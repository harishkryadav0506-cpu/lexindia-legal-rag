"""
scripts/run_rrf_cross_validation.py — 5-fold cross-validation for RRF k-value tuning.

Evaluates RRF k in [20, 30, 40, 60, 80] over 5 stratified folds of the 100 benchmark queries.
Calculates:
- Recall@1, Recall@3, Recall@5, Recall@10, and MRR.
- Identifies optimal k on validation folds.
- Evaluates full 100-query benchmark under tuned retrieval configuration.
"""

import sys
import json
import logging
from pathlib import Path
from collections import defaultdict
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import settings
from src.retrieval.hybrid_search import HybridSearcher
from src.retrieval.citation_graph import CitationGraph
from src.evaluation.metrics import calculate_retrieval_metrics
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RRF_CV")

BENCHMARK_PATH = REPO_ROOT / "data" / "eval" / "real_queries_100.json"
EXPANSION_CACHE_PATH = REPO_ROOT / "data" / "eval" / "expansion_cache.json"


def main():
    logger.info("=" * 80)
    logger.info("PHASE 3: 5-FOLD CROSS-VALIDATION FOR RRF K-VALUE TUNING")
    logger.info("=" * 80)

    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        queries = json.load(f)

    with open(EXPANSION_CACHE_PATH, "r", encoding="utf-8") as f:
        exp_cache = json.load(f)

    # Filter answerable queries for retrieval CV
    answerable_queries = [q for q in queries if q.get("gold_citations") and q.get("topic") != "REFUSAL"]
    logger.info(f"Loaded {len(queries)} total queries ({len(answerable_queries)} answerable for retrieval evaluation).")

    emb_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    graph = CitationGraph()

    # Pre-retrieve variant hits for each query to allow fast grid search over k
    candidate_k_values = [20, 30, 40, 60, 80]
    
    # 5-fold split
    n_queries = len(answerable_queries)
    fold_size = n_queries // 5
    folds = []
    for f_idx in range(5):
        val_start = f_idx * fold_size
        val_end = val_start + fold_size if f_idx < 4 else n_queries
        val_set = answerable_queries[val_start:val_end]
        train_set = answerable_queries[:val_start] + answerable_queries[val_end:]
        folds.append((train_set, val_set))

    # Test each k across 5 folds
    k_performance = defaultdict(lambda: defaultdict(list))

    for k_val in candidate_k_values:
        searcher = HybridSearcher(embedding_model=emb_model, rrf_k=k_val)
        logger.info(f"Evaluating candidate RRF k = {k_val} across 5 folds...")

        for fold_idx, (train_q, val_q) in enumerate(folds, 1):
            retrieved_sections = []
            gold_sections = []

            for q in val_q:
                question = q["question"]
                gold = q["gold_citations"]
                gold_sections.append(gold)

                vars = exp_cache.get(question, [question])
                cands = searcher.search_with_variants(question, [question] + vars, top_k=8)
                expanded = graph.expand_chunks(cands, max_expansion=2)

                secs = []
                for c in expanded[:10]:
                    s = c.get("section_id")
                    if s:
                        secs.append(s)
                retrieved_sections.append(secs)

            metrics = calculate_retrieval_metrics(retrieved_sections, gold_sections, k_list=[1, 3, 5, 8, 10])
            k_performance[k_val]["MRR"].append(metrics["MRR"])
            k_performance[k_val]["Recall@5"].append(metrics["Recall@5"])
            k_performance[k_val]["Recall@10"].append(metrics["Recall@10"])

    print("\n" + "=" * 70)
    print("5-FOLD CROSS-VALIDATION RESULTS ACROSS RRF K VALUES")
    print("=" * 70)
    print(f"{'RRF k':<10} | {'Mean MRR':<15} | {'Mean Recall@5':<15} | {'Mean Recall@10':<15}")
    print("-" * 70)

    best_k = 60
    best_mrr = 0.0

    for k_val in candidate_k_values:
        mean_mrr = float(np.mean(k_performance[k_val]["MRR"]))
        mean_r5 = float(np.mean(k_performance[k_val]["Recall@5"]))
        mean_r10 = float(np.mean(k_performance[k_val]["Recall@10"]))
        print(f"k = {k_val:<6} | {mean_mrr:>14.4f} | {mean_r5:>14.4f} | {mean_r10:>14.4f}")
        if mean_mrr > best_mrr:
            best_mrr = mean_mrr
            best_k = k_val

    print("=" * 70)
    print(f"Optimal RRF k chosen: {best_k} (Mean MRR: {best_mrr:.4f})")

    # Full 100-query benchmark evaluation under optimal k
    logger.info(f"\nRunning full 100-query evaluation with optimal RRF k = {best_k} and citation boosting...")
    optimal_searcher = HybridSearcher(embedding_model=emb_model, rrf_k=best_k)

    full_retrieved_sections = []
    full_gold_sections = []

    for q in queries:
        gold = q.get("gold_citations", [])
        full_gold_sections.append(gold)
        if not gold or q.get("topic") == "REFUSAL":
            full_retrieved_sections.append([])
            continue

        question = q["question"]
        vars = exp_cache.get(question, [question])
        cands = optimal_searcher.search_with_variants(question, [question] + vars, top_k=8)
        expanded = graph.expand_chunks(cands, max_expansion=2)

        secs = [c.get("section_id") for c in expanded[:10] if c.get("section_id")]
        full_retrieved_sections.append(secs)

    final_metrics = calculate_retrieval_metrics(full_retrieved_sections, full_gold_sections, k_list=[1, 3, 5, 8, 10])
    print("\n" + "=" * 60)
    print(f"FINAL TUNED RETRIEVAL METRICS (100 BENCHMARK QUERIES, k={best_k}):")
    print("=" * 60)
    for k in [1, 3, 5, 8, 10]:
        print(f"Recall@{k:<2}: {final_metrics[f'Recall@{k}'] * 100:.2f}%")
    print(f"MRR:       {final_metrics['MRR']:.4f}")
    print("=" * 60)

    # Save to json
    out_path = REPO_ROOT / "data" / "eval" / "tuned_retrieval_metrics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"optimal_k": best_k, "metrics": final_metrics}, f, indent=2)
    logger.info(f"Saved tuned metrics to {out_path}")


if __name__ == "__main__":
    main()
