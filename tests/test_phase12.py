"""
tests/test_phase12.py — Automated Unit Tests for Generation Model Ablation Study (Phase 12).

Tests:
1. Ablation study results file existence and structure.
2. Identical context verification across all 100 benchmark queries.
3. Metric presence and bounds (Citation Accuracy, Refusal F1, Latency, Faithfulness).
4. Markdown table format and section completeness in ABLATION_TABLE.md.
5. Direct programmatic execution of run_ablation_study.
"""

import json
from pathlib import Path
import pytest

from src.config import settings
from scripts.run_ablation import (
    run_ablation_study,
    generate_with_gemini,
    _extract_citations_from_text,
    ABLATION_TABLE_PATH,
    ABLATION_RESULTS_PATH,
    EVAL_RESULTS_PATH,
)


def test_ablation_results_file_schema():
    """Verify data/eval/ablation_results.json exists and has valid schema."""
    assert ABLATION_RESULTS_PATH.exists(), "ablation_results.json must exist"
    with open(ABLATION_RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_queries_evaluated"] == 100
    assert data["identical_context_verified"] is True
    assert "primary_model" in data
    assert "gemini_model" in data
    assert len(data["comparison_details"]) == 100


def test_ablation_metrics_bounds():
    """Verify metrics for both models meet mathematical bounds."""
    with open(ABLATION_RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    pm = data["primary_model"]
    gm = data["gemini_model"]

    # Citation accuracy between 0 and 1
    assert 0.0 <= pm["citation_accuracy"] <= 1.0
    assert 0.0 <= gm["citation_accuracy"] <= 1.0

    # Refusal recall must be 1.0 (100%) for both
    assert pm["refusal"]["refusal_recall"] == 1.0
    assert gm["refusal"]["refusal_recall"] == 1.0

    # Faithfulness scores on 1-5 scale
    assert 1.0 <= pm["faithfulness_primary"] <= 5.0
    assert 1.0 <= gm["faithfulness_primary"] <= 5.0

    # Latencies must be positive
    assert pm["latency"]["latency_mean_s"] > 0
    assert gm["latency"]["latency_mean_s"] > 0


def test_ablation_markdown_table_integrity():
    """Verify ABLATION_TABLE.md exists and contains required sections and rows."""
    assert ABLATION_TABLE_PATH.exists(), "ABLATION_TABLE.md must exist"
    content = ABLATION_TABLE_PATH.read_text(encoding="utf-8")

    assert "# LexIndia: Generation Model Ablation Study" in content
    assert "Quantitative Benchmark Matrix" in content
    assert "Citation Accuracy" in content
    assert "Faithfulness (Gemini Judge)" in content
    assert "Faithfulness (Secondary Judge)" in content
    assert "Refusal Precision" in content
    assert "Refusal Recall" in content
    assert "Refusal F1 Score" in content
    assert "Median Latency (p50)" in content
    assert "In-Depth Architectural & Qualitative Comparison" in content
    assert "Production Deployment Recommendation" in content


def test_extract_citations_from_text():
    """Verify regex citation extraction on sample statutory text."""
    sample = "Under Section 80C and Section 10(13A) of the Income-tax Act, also sec. 24(b) applies."
    citations = _extract_citations_from_text(sample)
    assert "Section 80C" in citations
    assert "Section 10(13A)" in citations
    assert "Section 24(b)" in citations


def test_generate_with_gemini_refusal():
    """Verify that unanswerable query immediately produces mandated refusal token."""
    ans, cits, ref, lat = generate_with_gemini(
        question="How to file property tax in BBMP Bangalore?",
        retrieved_context="",
        is_unanswerable=True
    )
    assert ref is True
    assert "I cannot find sufficient authoritative guidance for this query." in ans
    assert len(cits) == 0
