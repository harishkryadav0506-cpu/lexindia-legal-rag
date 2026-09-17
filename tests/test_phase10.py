"""
tests/test_phase10.py — Automated Unit Tests for Phase 10 (Evaluation Subsystem).

Tests:
1. real_queries_100.json structure, count, schema, URL provenance, and gold citation integrity.
2. Retrieval metrics calculation (Recall@K, MRR).
3. Citation accuracy calculation.
4. Refusal metrics calculation (Precision, Recall, F1).
5. Latency percentile calculations.
6. LLM Judge JSON output parsing and agreement metrics.
7. Human-in-the-loop review store metrics integration.
"""

import json
from pathlib import Path
import pytest

from src.evaluation.metrics import (
    calculate_retrieval_metrics,
    calculate_citation_accuracy,
    calculate_refusal_metrics,
    calculate_latency_stats,
    get_human_loop_metrics,
)
from src.evaluation.llm_judge import (
    _parse_judge_json,
    calculate_judge_agreement_metrics,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = REPO_ROOT / "data" / "eval" / "real_queries_100.json"
CHUNKS_FILE = REPO_ROOT / "data" / "processed" / "chunks.jsonl"


def test_eval_set_existence_and_count():
    """Verify that real_queries_100.json exists and has exactly 100 queries."""
    assert EVAL_FILE.exists(), f"Missing {EVAL_FILE}"
    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 100, f"Expected exactly 100 queries, found {len(data)}"


def test_eval_set_schema_and_refusal_distribution():
    """Verify schema, URL validity, and exactly 15 refusal queries."""
    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    refusal_count = 0
    answerable_count = 0
    valid_topics = {"DEDUCTION", "CALCULATION", "TDS_TCS", "CAPITAL_GAINS", "PROCEDURE", "REFUSAL"}

    for item in data:
        assert "id" in item
        assert "question" in item and len(item["question"]) > 5
        assert "source_forum_url" in item
        assert item["source_forum_url"].startswith("http"), f"Invalid URL in query #{item['id']}"
        assert "gold_citations" in item
        assert item.get("topic") in valid_topics, f"Invalid topic in query #{item['id']}"

        if item["topic"] == "REFUSAL":
            refusal_count += 1
            assert len(item["gold_citations"]) == 0, f"Refusal query #{item['id']} has citations!"
        else:
            answerable_count += 1
            assert len(item["gold_citations"]) > 0, f"Answerable query #{item['id']} missing gold citations!"

    assert refusal_count == 15, f"Expected exactly 15 refusal queries, got {refusal_count}"
    assert answerable_count == 85, f"Expected exactly 85 answerable queries, got {answerable_count}"


def test_gold_citations_present_in_corpus():
    """Verify all gold citations across answerable queries exist in chunks.jsonl."""
    assert CHUNKS_FILE.exists()
    corpus_sections = set()
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                sec = c.get("section_id")
                if sec:
                    corpus_sections.add(sec)

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        for gold_sec in item.get("gold_citations", []):
            assert gold_sec in corpus_sections, (
                f"Gold citation '{gold_sec}' in query #{item['id']} is NOT in corpus!"
            )


def test_calculate_retrieval_metrics():
    """Verify Recall@K and MRR computation."""
    retrieved = [
        ["Section 80C", "Section 10(13A)", "Section 24(b)"],  # rank 1 hit
        ["Section 44AB", "Section 115BAC", "Section 80C"],   # rank 3 hit
        ["Section 194C", "Section 192", "Section 194J"],     # miss
    ]
    gold = [
        ["Section 80C"],
        ["Section 80C"],
        ["Section 54"],
    ]

    m = calculate_retrieval_metrics(retrieved, gold, k_list=[1, 2, 3])
    # Query 1: hit at 1 (RR=1.0)
    # Query 2: hit at 3 (RR=1/3=0.3333)
    # Query 3: miss (RR=0.0)
    # MRR = (1 + 0.3333 + 0) / 3 = 0.4444
    assert pytest.approx(m["MRR"], rel=1e-3) == (1.0 + 1/3) / 3
    assert pytest.approx(m["Recall@1"], rel=1e-3) == 1 / 3
    assert pytest.approx(m["Recall@3"], rel=1e-3) == 2 / 3


def test_calculate_citation_accuracy():
    """Verify Citation Accuracy computation."""
    generated = [
        ["Section 80C", "Section 10(13A)"],  # Hit
        ["Section 194C"],                     # Miss
        ["Section 54", "Section 54F"],        # Hit
    ]
    gold = [
        ["Section 80C"],
        ["Section 80D"],
        ["Section 54"],
    ]
    res = calculate_citation_accuracy(generated, gold)
    assert pytest.approx(res["citation_accuracy"], rel=1e-3) == 2 / 3
    assert res["evaluated_answers"] == 3


def test_calculate_refusal_metrics():
    """Verify Refusal precision, recall, and F1 calculations."""
    predicted = [True, False, True, False]
    gold_unanswerable = [True, True, False, False]
    # TP: idx 0 (pred True, gold True)
    # FN: idx 1 (pred False, gold True)
    # FP: idx 2 (pred True, gold False)
    # TN: idx 3 (pred False, gold False)
    # Precision = 1 / (1 + 1) = 0.5
    # Recall = 1 / (1 + 1) = 0.5
    # F1 = 0.5
    res = calculate_refusal_metrics(predicted, gold_unanswerable)
    assert res["refusal_precision"] == 0.5
    assert res["refusal_recall"] == 0.5
    assert res["refusal_f1"] == 0.5


def test_calculate_latency_stats():
    """Verify latency percentile calculations."""
    latencies_ms = [1000, 2000, 3000, 4000, 5000]
    stats = calculate_latency_stats(latencies_ms)
    assert stats["latency_p50_s"] == 3.0
    assert stats["latency_mean_s"] == 3.0
    assert stats["latency_p90_s"] > 3.0


def test_parse_judge_json():
    """Verify LLM judge JSON extraction from diverse LLM output shapes."""
    # Clean JSON
    j1 = _parse_judge_json('{"score": 5, "reason": "Accurate grounding."}')
    assert j1["score"] == 5
    assert "Accurate" in j1["reason"]

    # Markdown fenced JSON
    j2 = _parse_judge_json('```json\n{"score": 4, "reason": "Good citations."}\n```')
    assert j2["score"] == 4

    # Text wrapping JSON
    j3 = _parse_judge_json('The evaluation is as follows:\n{"score": 2, "reason": "Unfaithful."}\nDone.')
    assert j3["score"] == 2


def test_judge_agreement_metrics():
    """Verify calculation of inter-judge agreement rates."""
    primary = [5, 4, 3, 5, 2]
    secondary = [5, 5, 3, 4, 1]
    # Diffs: [0, 1, 0, 1, 1] -> all <= 1 point (100% agreement within 1)
    res = calculate_judge_agreement_metrics(primary, secondary)
    assert res["agreement_within_1pt"] == 100.0
    assert res["exact_match_rate"] == 40.0
    assert res["mean_abs_diff"] == 0.6


def test_get_human_loop_metrics_integration():
    """Verify live retrieval of review metrics from review store."""
    metrics = get_human_loop_metrics()
    assert isinstance(metrics, dict)
    assert "approval_rate" in metrics
    assert "total_reviews" in metrics
    assert metrics["total_reviews"] >= 0
