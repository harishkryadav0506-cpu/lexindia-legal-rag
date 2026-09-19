"""
tests/test_citation_grounding.py — Test suite for Phase 4 Strict Citation Grounding & Refusal Logic.

Verifies:
1. CitationVerifierAgent parses [C#] tags and detects hallucinated citations.
2. RetryGeneration is triggered on first failure with corrective prompt feedback.
3. Escalation to Human Review (review_required=True / interrupt) triggers after 2 failed verification attempts.
4. Refusal logic is relaxed: answerable queries with valid retrieved chunks are answered with citations rather than falsely refused.
5. In-generator retry guardrail corrects invalid tags or false refusals.
"""

import pytest
from typing import List, Dict, Any

from src.agents.state import LexIndiaState
from src.agents.citation_verifier import CitationVerifierAgent
from src.agents.graph import LexIndiaGraphBuilder, route_citation_verifier
from src.generation.generator import AnswerGenerator
from src.generation.prompts import EXACT_REFUSAL_PHRASE, STANDARD_DISCLAIMER


@pytest.fixture
def mock_chunks() -> List[Dict[str, Any]]:
    return [
        {
            "chunk_id": "chunk_sec10_13a_001",
            "section_id": "Section 10(13A)",
            "act_name": "Income-tax Act, 1961",
            "doc_type": "statute",
            "source_url": "https://incometaxindia.gov.in/act/sec10_13a",
            "page_number": 12,
            "text": "Any special allowance specifically granted to an assessee by his employer to meet expenditure incurred on payment of rent in respect of residential accommodation occupied by him is exempt subject to limits.",
            "final_score": 0.88,
            "rerank_score": 0.88
        },
        {
            "chunk_id": "chunk_sec24b_001",
            "section_id": "Section 24(b)",
            "act_name": "Income-tax Act, 1961",
            "doc_type": "statute",
            "source_url": "https://incometaxindia.gov.in/act/sec24b",
            "page_number": 45,
            "text": "Where property has been acquired, constructed, repaired, renewed or reconstructed with borrowed capital, the amount of any interest payable on such capital is deductible up to two lakh rupees for self-occupied property.",
            "final_score": 0.82,
            "rerank_score": 0.82
        },
        {
            "chunk_id": "chunk_rule2a_001",
            "section_id": "Rule 2A",
            "act_name": "Income-tax Rules, 1962",
            "doc_type": "rules",
            "source_url": "https://incometaxindia.gov.in/rules/rule2a",
            "page_number": 3,
            "text": "The amount which is not included in the total income under clause (13A) of section 10 shall be the least of actual HRA, rent paid over 10% salary, or 50%/40% of salary.",
            "final_score": 0.79,
            "rerank_score": 0.79
        }
    ]


def test_citation_verifier_blocks_hallucinations(mock_chunks):
    """
    Test that CitationVerifierAgent:
    1. Detects hallucinated citations (e.g., [C5] when only 3 chunks exist).
    2. Sets corrective feedback on attempt 1.
    3. Escalates to human review (review_required=True) on attempt 2.
    """
    verifier = CitationVerifierAgent()

    # Case A: Hallucinated [C5] on 3-chunk context
    state_attempt_1: LexIndiaState = {
        "question": "What is the HRA exemption and interest deduction limit?",
        "financial_year": "2024-25",
        "taxpayer_type": "Individual (Salaried)",
        "require_review": False,
        "mock_429": False,
        "thread_id": "test_thread_001",
        "route": "DEDUCTION",
        "review_required": False,
        "reviewer_decision": None,
        "retrieved_chunks": mock_chunks,
        "calculation_result": None,
        "draft_answer": "Under Section 10(13A) [C1] and Rule 2A [C3], HRA is exempt. Also under Section 80C [C5], deductions are allowed.",
        "final_answer": "",
        "citations": [],
        "confidence": 0.85,
        "must_refuse": False,
        "refused": False,
        "low_confidence": False,
        "citation_retry_count": 0,
        "citation_verifier_feedback": None,
        "hallucinated_citations": [],
        "verified_citations": [],
        "fallback_used": False,
        "fallback_model": None,
        "agent_trace": [],
        "total_latency_ms": 0
    }

    res_1 = verifier.run(state_attempt_1)

    assert res_1["hallucinated_citations"] == ["[C5]"], "Expected [C5] to be flagged as hallucinated"
    assert res_1["citation_retry_count"] == 1
    assert res_1["review_required"] is False, "First failure should not yet trigger review_required"
    assert res_1["citation_verifier_feedback"] is not None
    assert "Rewrite using only C1-C3" in res_1["citation_verifier_feedback"]

    # Verify conditional router routes back to generator
    route_target = route_citation_verifier(res_1)
    assert route_target == "generator", "Attempt 1 failure should route to generator for retry"

    # Case B: Second failure (attempt 2)
    state_attempt_2 = dict(res_1)
    state_attempt_2["draft_answer"] = "Under Section 10(13A) [C1] and Section 80D [C4], medical insurance applies."

    res_2 = verifier.run(state_attempt_2)

    assert res_2["hallucinated_citations"] == ["[C4]"]
    assert res_2["citation_retry_count"] == 2
    assert res_2["review_required"] is True, "Second failure must escalate review_required to True"

    # Verify conditional router escalates to human_review
    route_target_2 = route_citation_verifier(res_2)
    assert route_target_2 == "human_review", "Attempt 2 failure must escalate to human_review node"


def test_citation_verifier_passes_valid_citations(mock_chunks):
    """Test that CitationVerifierAgent passes when all cited tags are in bounds [C1..C3]."""
    verifier = CitationVerifierAgent()

    state: LexIndiaState = {
        "question": "Can I claim both HRA and home loan interest?",
        "financial_year": "2024-25",
        "taxpayer_type": "Individual (Salaried)",
        "require_review": False,
        "mock_429": False,
        "thread_id": "test_thread_002",
        "route": "DEDUCTION",
        "review_required": False,
        "reviewer_decision": None,
        "retrieved_chunks": mock_chunks,
        "calculation_result": None,
        "draft_answer": "Under Section 10(13A) [C1] and Rule 2A [C3], HRA is exempt. Additionally, Section 24(b) [C2] provides deduction up to ₹2,00,000.",
        "final_answer": "",
        "citations": [],
        "confidence": 0.90,
        "must_refuse": False,
        "refused": False,
        "low_confidence": False,
        "citation_retry_count": 0,
        "citation_verifier_feedback": None,
        "hallucinated_citations": [],
        "verified_citations": [],
        "fallback_used": False,
        "fallback_model": None,
        "agent_trace": [],
        "total_latency_ms": 0
    }

    res = verifier.run(state)
    assert len(res["hallucinated_citations"]) == 0
    assert len(res["verified_citations"]) == 3
    assert res["citation_verifier_feedback"] is None
    assert route_citation_verifier(res) == "verifier", "Valid citations should proceed to verifier node"


def test_refusal_precision_on_answerable_queries(mock_chunks):
    """
    Test that AnswerGenerator:
    1. Does NOT falsely refuse answerable questions with relevant chunks.
    2. Properly extracts both regex Section citations and mapped [C#] sections.
    3. Correctly refuses when chunks are empty.
    """
    generator = AnswerGenerator()

    # 1. Answerable query with chunks
    res = generator.generate_answer(
        question="Can I claim both HRA exemption and deduction for home loan interest under Section 24(b)?",
        chunks=mock_chunks,
        financial_year="2024-25"
    )

    assert res["refused"] is False, "Answerable query with valid chunks must not be refused"
    assert EXACT_REFUSAL_PHRASE not in res["answer"], "Exact refusal phrase must not appear for answerable query"
    assert len(res["citations"]) > 0, "Expected at least one grounded citation"
    
    # Check that Section 10(13A) or Section 24(b) is identified in extracted_sections
    sections = res.get("extracted_sections", [])
    has_target_sec = any("10(13A)" in s or "24(b)" in s or "24" in s for s in sections)
    assert has_target_sec, f"Expected Section 10(13A) or 24(b) in extracted sections, got {sections}"

    # 2. Truly unanswerable query with zero chunks
    res_empty = generator.generate_answer(
        question="What are the customs import duties on precious gemstones under the Customs Tariff Act?",
        chunks=[],
        financial_year="2024-25"
    )

    assert res_empty["refused"] is True, "Query with zero chunks must be refused"
    assert EXACT_REFUSAL_PHRASE in res_empty["answer"]
