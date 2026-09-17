"""
src/evaluation/metrics.py — Evaluation metrics calculation for LexIndia Legal RAG.

Calculates:
- Recall@K (K=1, 3, 5, 8, 10)
- Mean Reciprocal Rank (MRR)
- Citation Accuracy (proportion of answers citing gold citations)
- Refusal Precision, Recall, and F1
- Latency percentiles (p50, p90, p95, mean)
- Human-in-the-loop review metrics from ReviewStore (reviews.db)
"""

from typing import List, Dict, Any, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


def calculate_retrieval_metrics(
    retrieved_sections_per_query: List[List[str]],
    gold_citations_per_query: List[List[str]],
    k_list: List[int] = [1, 3, 5, 8, 10],
) -> Dict[str, float]:
    """
    Computes Recall@K and MRR over answerable queries.
    Queries where gold_citations is empty are excluded from retrieval recall/MRR.
    """
    recalls_at_k: Dict[int, List[float]] = {k: [] for k in k_list}
    reciprocal_ranks: List[float] = []

    for retrieved, gold in zip(retrieved_sections_per_query, gold_citations_per_query):
        if not gold:
            continue  # Exclude refusal queries from standard retrieval recall

        gold_set = {g.strip().lower() for g in gold if g}
        if not gold_set:
            continue

        retrieved_clean = [r.strip().lower() for r in retrieved if r]

        # Calculate Recall@K
        for k in k_list:
            top_k_retrieved = retrieved_clean[:k]
            # Has at least one gold citation been retrieved?
            hit = any(g in top_k_retrieved for g in gold_set)
            recalls_at_k[k].append(1.0 if hit else 0.0)

        # Calculate Reciprocal Rank (first rank where gold citation appears, 1-indexed)
        rr = 0.0
        for rank, r in enumerate(retrieved_clean, start=1):
            if r in gold_set:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

    metrics = {}
    for k in k_list:
        vals = recalls_at_k[k]
        metrics[f"Recall@{k}"] = float(np.mean(vals)) if vals else 0.0

    metrics["MRR"] = float(np.mean(reciprocal_ranks)) if reciprocal_ranks else 0.0
    metrics["eval_query_count"] = len(reciprocal_ranks)

    return metrics


def calculate_citation_accuracy(
    generated_citations_per_query: List[List[str]],
    gold_citations_per_query: List[List[str]],
) -> Dict[str, float]:
    """
    Computes Citation Accuracy:
    Proportion of generated answers whose cited statutory sections cover at least one gold citation.
    """
    hits = []
    for gen, gold in zip(generated_citations_per_query, gold_citations_per_query):
        if not gold:
            continue  # Exclude refusal queries

        gold_set = {g.strip().lower() for g in gold if g}
        gen_clean = [g.strip().lower() for g in gen if g]

        # Did generated answer cite any gold section?
        hit = any(g in gen_clean for g in gold_set)
        hits.append(1.0 if hit else 0.0)

    accuracy = float(np.mean(hits)) if hits else 0.0
    return {
        "citation_accuracy": accuracy,
        "evaluated_answers": len(hits),
    }


def calculate_refusal_metrics(
    is_refusal_predicted: List[bool],
    is_unanswerable_gold: List[bool],
) -> Dict[str, float]:
    """
    Computes Refusal Precision, Recall, and F1.
    is_unanswerable_gold is True for refusal/ambiguous queries (len(gold_citations) == 0).
    """
    tp = sum(1 for p, g in zip(is_refusal_predicted, is_unanswerable_gold) if p and g)
    fp = sum(1 for p, g in zip(is_refusal_predicted, is_unanswerable_gold) if p and not g)
    fn = sum(1 for p, g in zip(is_refusal_predicted, is_unanswerable_gold) if not p and g)
    tn = sum(1 for p, g in zip(is_refusal_predicted, is_unanswerable_gold) if not p and not g)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "refusal_precision": float(precision),
        "refusal_recall": float(recall),
        "refusal_f1": float(f1),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
    }


def calculate_latency_stats(latencies_ms: List[float]) -> Dict[str, float]:
    """Computes latency percentiles and mean in seconds."""
    if not latencies_ms:
        return {"latency_mean_s": 0.0, "latency_p50_s": 0.0, "latency_p90_s": 0.0, "latency_p95_s": 0.0}

    arr = np.array(latencies_ms) / 1000.0  # convert ms to seconds
    return {
        "latency_mean_s": round(float(np.mean(arr)), 3),
        "latency_p50_s": round(float(np.percentile(arr, 50)), 3),
        "latency_p90_s": round(float(np.percentile(arr, 90)), 3),
        "latency_p95_s": round(float(np.percentile(arr, 95)), 3),
    }


def get_human_loop_metrics() -> Dict[str, Any]:
    """Retrieves live HITL statistics from the ReviewStore."""
    try:
        from src.agents.review_store import ReviewStore
        store = ReviewStore()
        return store.get_review_stats()
    except Exception as e:
        logger.warning(f"Could not load review store metrics: {e}")
        return {
            "approval_rate": 0.0,
            "edit_rate": 0.0,
            "reject_rate": 0.0,
            "avg_normalized_edit_distance": 0.0,
            "review_trigger_rate": 0.0,
            "total_reviews": 0,
            "total_decided": 0,
            "pending_count": 0,
        }
