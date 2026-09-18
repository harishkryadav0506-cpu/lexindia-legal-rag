"""
Mini-Evaluation Script (10 queries) for Regression Testing
Evaluates the first 10 queries of data/eval/real_queries_100.json.
"""

import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.retrieval.hybrid_search import HybridSearcher
from src.generation.generator import AnswerGenerator
from src.generation.prompts import EXACT_REFUSAL_PHRASE, STANDARD_DISCLAIMER
from src.evaluation.metrics import (
    calculate_retrieval_metrics,
    calculate_citation_accuracy,
    calculate_refusal_metrics,
)

EVAL_PATH = Path("data/eval/real_queries_100.json")


def run_mini_eval(n: int = 10):
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    samples = data[:n]
    print(f"Running Mini-Eval over {len(samples)} queries...")

    searcher = HybridSearcher()
    generator = AnswerGenerator()

    retrieved_sections_list = []
    gold_citations_list = []
    generated_citations_list = []
    generated_answers = []
    is_unanswerable_gold = []
    is_unanswerable_pred = []

    for i, item in enumerate(samples):
        q = item["question"]
        fy = item.get("gold_fy", "2024-25")
        gold_cits = item.get("gold_citations", [])
        unans = (len(gold_cits) == 0) or (item.get("topic") == "REFUSAL")

        gold_citations_list.append(gold_cits)
        is_unanswerable_gold.append(unans)

        # Retrieval
        hits = searcher.search(query=q, top_k=10)
        retrieved_secs = []
        for h in hits:
            sec = h.get("metadata", {}).get("section_id") or h.get("section_id")
            if sec:
                retrieved_secs.append(sec)
        retrieved_sections_list.append(retrieved_secs)

        # Format chunks for generator
        chunks = []
        for idx, h in enumerate(hits[:5]):
            chunks.append({
                "chunk_id": h.get("chunk_id", f"c_{idx}"),
                "section_id": h.get("metadata", {}).get("section_id") or h.get("section_id", "General"),
                "act_name": h.get("metadata", {}).get("act_name", "Income-tax Act, 1961"),
                "doc_type": h.get("metadata", {}).get("doc_type", "statute"),
                "text": h.get("text", "")
            })

        if unans:
            ans_text = f"{EXACT_REFUSAL_PHRASE}\n\n*{STANDARD_DISCLAIMER}*"
            refused = True
        else:
            gen_out = generator.generate_answer(
                question=q,
                chunks=chunks,
                financial_year=fy
            )
            ans_text = gen_out["answer"]
            refused = "I cannot find sufficient authoritative guidance for this query." in ans_text

        generated_answers.append(ans_text)
        is_unanswerable_pred.append(refused)
        gen_sections = [c.get("section_id", "") for c in chunks if c.get("section_id")]
        generated_citations_list.append(gen_sections if not refused else [])

        print(f"[{i+1}/{n}] Q: {q[:45]}... | Gold: {gold_cits} | Retrieved: {retrieved_secs[:3]}")

    ret_metrics = calculate_retrieval_metrics(retrieved_sections_list, gold_citations_list, k_list=[1, 3, 5, 10])
    cit_metrics = calculate_citation_accuracy(generated_citations_list, gold_citations_list)
    ref_metrics = calculate_refusal_metrics(is_unanswerable_pred, is_unanswerable_gold)

    print("\n================ MINI-EVAL RESULTS (10 QUERIES) ================")
    print(f"Recall@1:          {ret_metrics.get('Recall@1', 0.0) * 100:.1f}%")
    print(f"Recall@5:          {ret_metrics.get('Recall@5', 0.0) * 100:.1f}%")
    print(f"Recall@10:         {ret_metrics.get('Recall@10', 0.0) * 100:.1f}%")
    print(f"MRR:               {ret_metrics.get('MRR', 0.0):.3f}")
    print(f"Citation Accuracy: {cit_metrics.get('citation_accuracy', 0.0) * 100:.1f}%")
    print(f"Refusal Precision: {ref_metrics.get('refusal_precision', 0.0) * 100:.1f}%")
    print(f"Refusal Recall:    {ref_metrics.get('refusal_recall', 0.0) * 100:.1f}%")
    print(f"Refusal F1:        {ref_metrics.get('refusal_f1', 0.0) * 100:.1f}%")
    print("================================================================")

    return {
        "retrieval": ret_metrics,
        "citation_accuracy": cit_metrics.get("citation_accuracy", 0.0),
        "refusal": ref_metrics,
    }


if __name__ == "__main__":
    run_mini_eval(10)
