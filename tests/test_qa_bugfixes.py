"""
tests/test_qa_bugfixes.py — Regression test suite for the 9 manual QA bugs.
"""

import pytest
from src.generation.generator import (
    clean_and_repair_truncation,
    enforce_low_confidence_hedging,
    enforce_fy_conflict_notice,
)
from src.generation.prompts import EXACT_REFUSAL_PHRASE, STANDARD_DISCLAIMER
from src.agents.compliance_verifier import ComplianceVerifierAgent


def test_bug1_truncation_cleanup():
    """BUG 1: Truncation mid-word and mid-citation tag must be cleanly repaired."""
    # Test case 1: Incomplete citation tag at end
    truncated_text = (
        "Deduction is available under Section 80C, Section 80CCC and Section 80CCD(1) [C2][C3][C4][C"
    )
    repaired = clean_and_repair_truncation(truncated_text)
    assert not repaired.endswith("[C")
    assert "[C4]" in repaired
    assert STANDARD_DISCLAIMER in repaired

    # Test case 2: Mid-sentence cut off
    cut_sentence = "Under Section 80C, the deduction ceiling is Rs 1,50,000 per financial year [C1]. In addition, Section 80CCD allows addit"
    repaired2 = clean_and_repair_truncation(cut_sentence)
    assert "allows addit" not in repaired2
    assert repaired2.startswith("Under Section 80C, the deduction ceiling is Rs 1,50,000 per financial year [C1].")
    assert STANDARD_DISCLAIMER in repaired2

    # Test case 3: Never show an unclosed citation bracket
    assert "[" not in repaired.split("]")[-1]


def test_bug2_low_confidence_chunk_hedging():
    """BUG 2: Claims citing chunks with retrieval score < 0.05 must be qualified/hedged."""
    chunks = [
        {"chunk_id": "c1", "section_id": "Section 80C", "final_score": 0.85, "text": "Section 80C allows deduction."},
        {"chunk_id": "c7", "section_id": "Historical Note", "final_score": 0.0084, "text": "Section 80C was introduced in 2023."}
    ]
    raw_answer = "Section 80C allows deduction up to 1.5 Lakh [C1].\nSection 80C was introduced in 2023 to allow deductions [C2]."
    hedged = enforce_low_confidence_hedging(raw_answer, chunks)
    assert "Low-confidence" in hedged
    assert "*(Note: Low-confidence excerpt)*" in hedged


def test_bug3_and_bug4_low_entailment_must_refuse():
    """BUG 3 & 4: Moderate/high rerank score (0.6063) must refuse if entailment < 0.50."""
    class MockGateLowEntailment:
        def verify_answer(self, draft, chunks):
            return {
                "mean_entailment": 0.39,  # Under 0.50 threshold
                "is_faithful": False,
                "unsupported_citations": [],
                "sentence_scores": [{"sentence": draft, "score": 0.39}]
            }

    verifier = ComplianceVerifierAgent(faithfulness_gate=MockGateLowEntailment())
    mock_state = {
        "draft_answer": "The new regime tax slabs for FY 2024-25 are 0-3L nil, 3-7L 5% per Section 10 [C1].",
        "retrieved_chunks": [
            {"chunk_id": "c1", "rerank_score": 0.6063, "score": 0.6063, "text": "Section 10 exempt income provisions."}
        ],
        "refused": False,
        "review_required": False,
        "agent_trace": []
    }
    verified = verifier.run(mock_state)
    assert verified["must_refuse"] is True
    assert verified["refused"] is True
    assert EXACT_REFUSAL_PHRASE in verified["final_answer"]
    assert verified["confidence"] <= 0.25


def test_bug7_fy_conflict_notice():
    """BUG 7: Question FY differing from dropdown FY must include explicit note."""
    question = "What are the new regime tax slabs for FY 2025-26?"
    dropdown_fy = "2024-25"
    raw_answer = "The tax slabs under Section 115BAC are provided below [C1]."

    noted = enforce_fy_conflict_notice(raw_answer, question, dropdown_fy)
    assert "Note: Answer evaluated for selected Financial Year 2024-25" in noted
    assert "Statutory provisions for 2025-26 may differ" in noted


def test_bug9_telemetry_refused_flag():
    """BUG 9: Refused flag must be True when final answer is a refusal."""
    class MockGatePassing:
        def verify_answer(self, draft, chunks):
            return {"mean_entailment": 1.0, "is_faithful": True}

    verifier = ComplianceVerifierAgent(faithfulness_gate=MockGatePassing())
    mock_state = {
        "draft_answer": f"{EXACT_REFUSAL_PHRASE}\n\n*{STANDARD_DISCLAIMER}*",
        "retrieved_chunks": [{"chunk_id": "c1", "rerank_score": 0.04, "score": 0.04, "text": "..."}],
        "refused": False,
        "review_required": False,
        "agent_trace": []
    }
    verified = verifier.run(mock_state)
    assert verified["refused"] is True
    assert verified["must_refuse"] is True
    # Telemetry entry outputs_summary must show Refused: True
    last_trace = verified["agent_trace"][-1]
    assert "Refused: True" in last_trace["outputs_summary"]


def test_p1_refusal_overwrites_draft_and_clears_citations():
    """P1 / BUG A: When must_refuse is True, draft_answer must also be overwritten with refusal and citations cleared."""
    class MockGateFailing:
        def verify_answer(self, draft, chunks):
            return {"mean_entailment": 0.14, "is_faithful": False}

    verifier = ComplianceVerifierAgent(faithfulness_gate=MockGateFailing())
    mock_state = {
        "draft_answer": "Fabricated tax slab table | 0-3L | Nil | [C1]\n| 3-6L | 5% | [C1]",
        "retrieved_chunks": [{"chunk_id": "c1", "rerank_score": 0.71, "score": 0.60, "text": "..."}],
        "citations": [{"citation_id": "[C1]", "section_id": "Section 10"}],
        "refused": False,
        "review_required": False,
        "agent_trace": []
    }
    verified = verifier.run(mock_state)
    assert verified["must_refuse"] is True
    assert verified["refused"] is True
    assert EXACT_REFUSAL_PHRASE in verified["draft_answer"]
    assert EXACT_REFUSAL_PHRASE in verified["final_answer"]
    assert "Fabricated" not in verified["draft_answer"]
    assert "Fabricated" not in verified["final_answer"]
    assert verified["citations"] == []


def test_p4_citation_section_mismatch_dropped():
    """P4 / FIX 3: Citation tag is dropped when cited chunk section does not match section in sentence."""
    from src.agents.citation_verifier import CitationVerifierAgent
    verifier = CitationVerifierAgent()
    mock_state = {
        "draft_answer": "Relief under Section 88 was previously provided [C1]. In contrast, Section 80C provides a deduction [C2].",
        "retrieved_chunks": [
            {"chunk_id": "c1", "section_id": "Section 79", "text": "Carry forward of losses under section 79."},
            {"chunk_id": "c2", "section_id": "Section 80C", "text": "Deductions in respect of life insurance premia, etc."}
        ],
        "citation_retry_count": 0,
        "agent_trace": []
    }
    result = verifier.run(mock_state)
    # [C1] cited in Section 88 sentence had chunk Section 79 -> mismatch -> dropped
    # [C2] cited in Section 80C sentence had chunk Section 80C -> match -> retained
    assert "[C1]" not in result["draft_answer"]
    assert "[C2]" in result["draft_answer"]
    assert "Section 88" in result["draft_answer"]


def test_p5_table_hedging_clean():
    """P5 / FIX 4: Hedging qualifiers must not corrupt markdown table rows."""
    chunks = [
        {"chunk_id": "c1", "section_id": "Section 80C", "final_score": 0.01, "text": "..."}
    ]
    markdown_with_table = (
        "Here are the details [C1]:\n"
        "| Slab | Rate |\n"
        "| 0-3L | Nil |\n"
        "| 3-6L | 5% |"
    )
    hedged = enforce_low_confidence_hedging(markdown_with_table, chunks)
    # Table rows should not have injected hedge text inside cells
    lines = [line.strip() for line in hedged.split("\n") if line.strip()]
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            assert "Low-confidence" not in line


def test_p6_fy_notice_only_on_mismatch():
    """P6 / FIX 5: FY conflict notice only present when question FY differs from dropdown."""
    # When query has matching FY, no notice
    q_match = "What is the slab for FY 2024-25?"
    ans_match = enforce_fy_conflict_notice("The slabs are as follows [C1].", q_match, "2024-25")
    assert "Note: Answer evaluated for selected Financial Year" not in ans_match

    # When query has no FY, no notice
    q_none = "What is Section 80C limit?"
    ans_none = enforce_fy_conflict_notice("Limit is 1.5 Lakh [C1].", q_none, "2024-25")
    assert "Note: Answer evaluated for selected Financial Year" not in ans_none

    # When query has different FY, notice present
    q_diff = "What was the slab for FY 2023-24?"
    ans_diff = enforce_fy_conflict_notice("The slabs are as follows [C1].", q_diff, "2024-25")
    assert "Note: Answer evaluated for selected Financial Year 2024-25" in ans_diff


def test_p11_review_store_thread_deduplication(tmp_path):
    """P11 / FIX 10: Repeat queries with identical (query, FY) reuse existing pending thread."""
    from src.agents.review_store import ReviewStore
    db_file = tmp_path / "test_reviews.db"
    store = ReviewStore(db_path=str(db_file))

    # Create first entry
    review_1 = store.create_review_entry(
        thread_id="thread-uuid-1",
        query="What is Section 80C limit?",
        financial_year="2024-25",
        taxpayer_type="Individual",
        draft_answer="Draft 1",
        citations=[],
        agent_trace=[],
        confidence=0.45
    )

    # Submit exact same query and FY while still pending with a new thread_id
    review_2 = store.create_review_entry(
        thread_id="thread-uuid-2",
        query="What is Section 80C limit?",
        financial_year="2024-25",
        taxpayer_type="Individual",
        draft_answer="Draft 2 updated",
        citations=[],
        agent_trace=[],
        confidence=0.50
    )

    # Must reuse thread-uuid-1
    assert review_1["thread_id"] == "thread-uuid-1"
    assert review_2["thread_id"] == "thread-uuid-1"

    # Verify only 1 pending review exists, and content was updated
    pending = store.get_pending_reviews()
    assert len(pending) == 1
    assert pending[0]["draft_answer"] == "Draft 2 updated"

