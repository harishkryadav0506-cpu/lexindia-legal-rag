"""
scripts/rerun_gemini_fallbacks_on_qwen.py — Re-runs the 6 fallback queries on qwen/qwen3.8-27b
now that the 15-minute sliding window has rolled off.
"""

import sys
import json
import time
import logging
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import settings
from src.retrieval.hybrid_search import HybridSearcher
from src.retrieval.citation_graph import CitationGraph
from src.generation.generator import AnswerGenerator
from src.agents.citation_verifier import CitationVerifierAgent
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RerunQwenFallbacks")

FALLBACK_IDS = [24, 27, 28, 36, 43, 53]

BENCHMARK_PATH = REPO_ROOT / "data" / "eval" / "real_queries_100.json"
EXPANSION_CACHE_PATH = REPO_ROOT / "data" / "eval" / "expansion_cache.json"
RESULTS_JSON_PATH = REPO_ROOT / "data" / "eval" / "eval_results.json"


def main():
    logger.info(f"Re-running {len(FALLBACK_IDS)} fallback queries on {settings.GENERATION_MODEL}...")

    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        queries = json.load(f)
    q_map = {q["id"]: q for q in queries}

    with open(EXPANSION_CACHE_PATH, "r", encoding="utf-8") as f:
        exp_cache = json.load(f)

    with open(RESULTS_JSON_PATH, "r", encoding="utf-8") as f:
        eval_results = json.load(f)

    qr_map = {r["id"]: r for r in eval_results.get("query_results", [])}

    emb_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    searcher = HybridSearcher(embedding_model=emb_model, rrf_k=40)
    graph = CitationGraph()
    generator = AnswerGenerator()
    verifier = CitationVerifierAgent()

    for idx, qid in enumerate(FALLBACK_IDS, 1):
        q = q_map[qid]
        question = q["question"]
        gold = q.get("gold_citations", [])
        gold_fy = q.get("gold_fy", "2024-25")

        logger.info(f"[{idx}/{len(FALLBACK_IDS)}] Qwen generating Q{qid}: {question[:50]}...")
        variants = exp_cache.get(question, [question])
        cands = searcher.search_with_variants(question, [question] + variants, top_k=8)
        expanded = graph.expand_chunks(cands, max_expansion=2)

        t0 = time.time()
        gen_out = generator.generate_answer(
            question=question,
            chunks=expanded[:8],
            financial_year=gold_fy,
            taxpayer_type="Individual (Salaried)"
        )
        lat_ms = int((time.time() - t0) * 1000)
        srv_model = gen_out.get("serving_model")
        logger.info(f"   -> Q{qid} serving_model: {srv_model} in {lat_ms}ms")

        if srv_model == settings.GENERATION_MODEL:
            rec = qr_map[qid]
            rec["answer"] = gen_out["answer"]
            rec["serving_model"] = srv_model
            rec["cached"] = False
            rec["fallback_used"] = False
            rec["generated_citations"] = gen_out.get("extracted_sections", [])

            v_state = {
                "question": question,
                "retrieved_chunks": expanded[:8],
                "draft_answer": gen_out["answer"],
                "citation_retry_count": 0,
                "review_required": False,
                "financial_year": gold_fy,
                "taxpayer_type": "Individual (Salaried)",
                "require_review": False,
                "mock_429": False,
                "thread_id": f"regen_q{qid}",
                "route": q.get("topic", "DEDUCTION"),
                "reviewer_decision": None,
                "calculation_result": None,
                "final_answer": "",
                "citations": [],
                "confidence": 0.85,
                "must_refuse": False,
                "refused": gen_out["refused"],
                "low_confidence": False,
                "citation_verifier_feedback": None,
                "hallucinated_citations": [],
                "verified_citations": [],
                "fallback_used": False,
                "fallback_model": None,
                "agent_trace": [],
                "total_latency_ms": lat_ms,
            }
            v_res = verifier.run(v_state)
            rec["verified_citations"] = v_res.get("verified_citations", [])
            qr_map[qid] = rec

    eval_results["query_results"] = [qr_map[q["id"]] for q in queries]
    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2, ensure_ascii=False)

    logger.info("Updated eval_results.json successfully.")


if __name__ == "__main__":
    main()
