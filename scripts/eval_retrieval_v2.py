"""
scripts/eval_retrieval_v2.py — Compare Retrieval Metrics on lexindia_corpus vs lexindia-v2.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from src.evaluation.metrics import calculate_retrieval_metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EvalRetrievalV2")

BENCHMARK_PATH = Path("data/eval/real_queries_100.json")

def evaluate_index(index_name: str, queries: list, model: SentenceTransformer, es: Elasticsearch):
    retrieved_sections = []
    gold_citations = []

    for q in queries:
        gold = q.get("gold_citations", [])
        gold_citations.append(gold)
        if not gold or q.get("topic") == "REFUSAL":
            retrieved_sections.append([])
            continue

        q_text = q["question"]
        q_emb = model.encode(q_text, normalize_embeddings=True).tolist()

        # Hybrid BM25 + kNN
        body = {
            "query": {
                "match": {
                    "text": q_text
                }
            },
            "knn": {
                "field": "embedding",
                "query_vector": q_emb,
                "k": 10,
                "num_candidates": 50
            },
            "size": 10
        }
        res = es.search(index=index_name, body=body)
        hits = res["hits"]["hits"]

        secs = []
        for h in hits:
            sec = h["_source"].get("section_id")
            if sec and sec != "General":
                secs.append(sec)
            for cit in h["_source"].get("citations", []):
                if cit.startswith("Section ") or cit.startswith("Rule "):
                    secs.append(cit)
        retrieved_sections.append(secs)

    metrics = calculate_retrieval_metrics(retrieved_sections, gold_citations, k_list=[1, 3, 5, 8, 10])
    return metrics

def main():
    es = Elasticsearch("http://localhost:9200")
    model = SentenceTransformer("BAAI/bge-base-en-v1.5")

    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        queries = json.load(f)

    logger.info(f"Loaded {len(queries)} queries. Evaluating baseline (lexindia_corpus)...")
    base_metrics = evaluate_index("lexindia_corpus", queries, model, es)

    logger.info("Evaluating new statutory index (lexindia-v2)...")
    v2_metrics = evaluate_index("lexindia-v2", queries, model, es)

    print("\n" + "=" * 60)
    print("RETRIEVAL COMPARISON OVER 100 QUERIES")
    print("=" * 60)
    print(f"{'Metric':<15} | {'Baseline (v1)':<15} | {'New Chunks (v2)':<15} | {'Delta':<10}")
    print("-" * 60)
    for k in [1, 3, 5, 8, 10]:
        b_val = base_metrics[f"Recall@{k}"] * 100
        v_val = v2_metrics[f"Recall@{k}"] * 100
        delta = v_val - b_val
        print(f"Recall@{k:<8} | {b_val:>13.1f}% | {v_val:>13.1f}% | {delta:>+8.1f}%")

    b_mrr = base_metrics["MRR"]
    v_mrr = v2_metrics["MRR"]
    print(f"{'MRR':<15} | {b_mrr:>14.3f} | {v_mrr:>14.3f} | {v_mrr - b_mrr:>+9.3f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
