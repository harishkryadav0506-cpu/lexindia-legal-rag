"""
tests/test_phase7.py — Test suite for LexIndia Phase 7 Human-in-the-Loop (HITL) Integration.

Strictly adheres to SPEC.md section #7, #9, and section #15 (Phase 7):
- Tests LangGraph human_review interrupt() and SqliteSaver checkpointing.
- Tests resume flow with:
  1. action = 'approve'
  2. action = 'edit' (verifies human_verified_pairs.json append)
  3. action = 'reject' (verifies refusal phrase and reviewer note)
- Tests ReviewStore CRUD, stats calculation, and normalized edit distance.
- Tests FastAPI endpoints:
  * POST /query (awaiting_review vs complete)
  * POST /reviews/{thread_id}/decision
  * GET /reviews/pending
  * GET /reviews/stats
  * GET /graph
"""

import json
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from src.config import settings
from src.agents import (
    run_query,
    resume_query_review,
    review_store,
)
from src.agents.review_store import ReviewStore, normalized_edit_distance
from src.generation.prompts import EXACT_REFUSAL_PHRASE
from src.api.main import app


@pytest.fixture
def temp_review_store(tmp_path):
    """Create isolated ReviewStore with temporary SQLite and verified pairs files."""
    db_file = tmp_path / "test_reviews.db"
    pairs_file = tmp_path / "human_verified_pairs.json"
    return ReviewStore(db_path=db_file, verified_pairs_path=pairs_file)


def test_normalized_edit_distance():
    # Identical strings
    assert normalized_edit_distance("Same string", "Same string") == 0.0
    # Empty strings
    assert normalized_edit_distance("", "") == 0.0
    # 1 substitution in length 5
    assert normalized_edit_distance("hello", "hallo") == 0.2
    # Distinct strings
    assert 0.0 < normalized_edit_distance("Old Tax Regime advice", "New Tax Regime advice") <= 1.0


def test_review_store_crud_and_lifecycle(temp_review_store):
    store = temp_review_store
    thread_id = f"test_{uuid.uuid4().hex[:8]}"

    # 1. Create review entry
    entry = store.create_review_entry(
        thread_id=thread_id,
        query="What is the Section 80C limit?",
        financial_year="2024-25",
        taxpayer_type="Individual",
        draft_answer="The deduction limit under Section 80C is Rs 1.5 Lakh.",
        citations=[{"section_id": "Section 80C", "doc_type": "statute"}],
        agent_trace=[{"agent": "SupervisorAgent", "action": "Routed to DEDUCTION", "latency_ms": 10, "inputs_summary": "", "outputs_summary": ""}],
        route="DEDUCTION",
        confidence=0.85,
        action="pending"
    )
    assert entry["thread_id"] == thread_id
    assert entry["action"] == "pending"

    # 2. Check pending list
    pending = store.get_pending_reviews()
    assert any(p["thread_id"] == thread_id for p in pending)
    target = next(p for p in pending if p["thread_id"] == thread_id)
    assert target["age_minutes"] >= 0.0

    # 3. Retrieve by thread_id
    fetched = store.get_review_by_thread_id(thread_id)
    assert fetched is not None
    assert fetched["query"] == "What is the Section 80C limit?"
    assert len(fetched["citations"]) == 1

    # 4. Record decision: approve
    updated = store.record_decision(
        thread_id=thread_id,
        action="approve",
        final_answer=entry["draft_answer"],
        reviewer_note="Approved without modifications"
    )
    assert updated["action"] == "approve"
    assert updated["final_answer"] == entry["draft_answer"]
    assert updated["reviewer_note"] == "Approved without modifications"

    # Pending list should now exclude this thread
    pending_after = store.get_pending_reviews()
    assert not any(p["thread_id"] == thread_id for p in pending_after)


def test_review_store_stats_calculation(temp_review_store):
    store = temp_review_store

    # Insert 3 reviews with different decisions
    t1 = f"t1_{uuid.uuid4().hex[:6]}"
    store.create_review_entry(t1, "Query 1", "2024-25", "Individual", "Draft 1", [], [])
    store.record_decision(t1, "approve", "Draft 1")

    t2 = f"t2_{uuid.uuid4().hex[:6]}"
    store.create_review_entry(t2, "Query 2", "2024-25", "Individual", "Draft 2 original text", [], [])
    store.record_decision(t2, "edit", "Draft 2 edited text by expert", reviewer_note="Corrected Section reference")

    t3 = f"t3_{uuid.uuid4().hex[:6]}"
    store.create_review_entry(t3, "Query 3", "2024-25", "Individual", "Draft 3", [], [])
    store.record_decision(t3, "reject", "Refusal note", reviewer_note="Inaccurate information")

    stats = store.get_review_stats()
    assert stats["total_reviews"] == 3
    assert stats["total_decided"] == 3
    assert stats["pending_count"] == 0
    assert stats["approval_rate"] == pytest.approx(1 / 3, rel=1e-2)
    assert stats["edit_rate"] == pytest.approx(1 / 3, rel=1e-2)
    assert stats["reject_rate"] == pytest.approx(1 / 3, rel=1e-2)
    assert stats["avg_normalized_edit_distance"] > 0.0


def test_human_verified_pairs_append_on_edit(temp_review_store):
    store = temp_review_store
    thread_id = f"t_verified_{uuid.uuid4().hex[:6]}"

    store.create_review_entry(
        thread_id=thread_id,
        query="Can I claim standard deduction under new tax regime in FY 2025-26?",
        financial_year="2025-26",
        taxpayer_type="Individual (Salaried)",
        draft_answer="Standard deduction is Rs 50,000.",
        citations=[{"section_id": "Section 16(ia)", "doc_type": "statute"}],
        agent_trace=[]
    )

    edited_text = "Yes, salaried individuals can claim a standard deduction of Rs 75,000 under the New Tax Regime per Finance Act 2024 / 2025 amendment to Section 16(ia)."
    store.record_decision(
        thread_id=thread_id,
        action="edit",
        final_answer=edited_text,
        reviewer_note="Updated standard deduction limit to Rs 75,000"
    )

    # Verify JSON file has been written
    assert store.verified_pairs_path.exists()
    with open(store.verified_pairs_path, "r", encoding="utf-8") as f:
        pairs = json.load(f)

    matching = [p for p in pairs if p["thread_id"] == thread_id]
    assert len(matching) == 1
    pair = matching[0]
    assert pair["query"] == "Can I claim standard deduction under new tax regime in FY 2025-26?"
    assert pair["final_answer"] == edited_text
    assert pair["action"] == "edit"
    assert pair["reviewer_note"] == "Updated standard deduction limit to Rs 75,000"
    assert len(pair["citations"]) == 1


def test_hitl_interrupt_and_resume_approve():
    # Run query requiring review
    res_awaiting = run_query(
        question="What is the Section 80C deduction limit for FY 2024-25?",
        financial_year="2024-25",
        require_review=True
    )

    assert res_awaiting["status"] == "awaiting_review"
    assert res_awaiting["review_required"] is True
    thread_id = res_awaiting["thread_id"]
    assert thread_id is not None
    assert len(res_awaiting["draft_answer"]) > 0

    # Verify thread exists in review_store
    record = review_store.get_review_by_thread_id(thread_id)
    assert record is not None
    assert record["action"] == "pending"

    # Resume with approve
    res_final = resume_query_review(
        thread_id=thread_id,
        action="approve"
    )

    assert res_final["status"] == "complete"
    assert res_final["thread_id"] == thread_id
    assert res_final["final_answer"] == res_awaiting["draft_answer"]
    assert res_final["action"] == "approve"

    # Verify review_store was updated
    updated_record = review_store.get_review_by_thread_id(thread_id)
    assert updated_record["action"] == "approve"


def test_hitl_interrupt_and_resume_edit():
    res_awaiting = run_query(
        question="Can I claim Section 80D deduction without health checkup?",
        financial_year="2024-25",
        require_review=True
    )

    assert res_awaiting["status"] == "awaiting_review"
    thread_id = res_awaiting["thread_id"]

    edited_answer = (
        "Under Section 80D, deduction up to Rs 25,000 is allowed for health insurance premiums. "
        "Preventive health check-up is allowed up to Rs 5,000 within the overall ceiling."
    )
    res_final = resume_query_review(
        thread_id=thread_id,
        action="edit",
        edited_answer=edited_answer,
        reviewer_note="Clarified preventive checkup limit within overall ceiling"
    )

    assert res_final["status"] == "complete"
    assert res_final["final_answer"] == edited_answer
    assert res_final["action"] == "edit"

    # Verify appended to human_verified_pairs.json
    verified_file = settings.EVAL_DATA_DIR / "human_verified_pairs.json"
    assert verified_file.exists()
    with open(verified_file, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    assert any(p["thread_id"] == thread_id and p["final_answer"] == edited_answer for p in pairs)


def test_hitl_interrupt_and_resume_reject():
    res_awaiting = run_query(
        question="Is cryptocurrency mining taxed at flat 30 percent?",
        financial_year="2024-25",
        require_review=True
    )

    assert res_awaiting["status"] == "awaiting_review"
    thread_id = res_awaiting["thread_id"]

    res_final = resume_query_review(
        thread_id=thread_id,
        action="reject",
        reviewer_note="Insufficient statutory chunk retrieved for virtual digital assets mining expenses"
    )

    assert res_final["status"] == "complete"
    assert res_final["action"] == "reject"
    assert res_final["refused"] is True
    assert EXACT_REFUSAL_PHRASE in res_final["final_answer"]
    assert "Reviewer note: Insufficient statutory chunk" in res_final["final_answer"]


def test_fastapi_query_and_review_workflow():
    client = TestClient(app)

    # 1. POST /query with require_review=True
    query_payload = {
        "question": "Deduction for home loan principal repayment under 80C",
        "financial_year": "2024-25",
        "require_review": True
    }
    resp1 = client.post("/query", json=query_payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "awaiting_review"
    assert data1["review_required"] is True
    thread_id = data1["thread_id"]
    assert thread_id is not None
    assert len(data1["draft_answer"]) > 0

    # 2. GET /reviews/pending
    resp_pending = client.get("/reviews/pending")
    assert resp_pending.status_code == 200
    pending_list = resp_pending.json()
    assert any(p["thread_id"] == thread_id for p in pending_list)

    # 3. POST /reviews/{thread_id}/decision
    decision_payload = {
        "action": "edit",
        "edited_answer": "Home loan principal repayment is deductible under Section 80C up to Rs 1.5 Lakh per financial year.",
        "reviewer_note": "Verified against Section 80C(2)(xviii)"
    }
    resp_dec = client.post(f"/reviews/{thread_id}/decision", json=decision_payload)
    assert resp_dec.status_code == 200
    data_dec = resp_dec.json()
    assert data_dec["status"] == "complete"
    assert data_dec["answer"] == decision_payload["edited_answer"]

    # 4. GET /reviews/stats
    resp_stats = client.get("/reviews/stats")
    assert resp_stats.status_code == 200
    stats = resp_stats.json()
    assert stats["total_decided"] >= 1
    assert "approval_rate" in stats
    assert "edit_rate" in stats
    assert "reject_rate" in stats


def test_fastapi_graph_endpoint():
    client = TestClient(app)
    resp = client.get("/graph?section_id=Section 80C&hops=2")
    assert resp.status_code == 200
    graph_data = resp.json()
    assert graph_data["section_id"] == "Section 80C"
    assert graph_data["hops"] == 2
    assert len(graph_data["nodes"]) > 0
    assert len(graph_data["edges"]) > 0
    node_keys = graph_data["nodes"][0].keys()
    assert "id" in node_keys
    assert "authority_level" in node_keys
    edge_keys = graph_data["edges"][0].keys()
    assert "source" in edge_keys
    assert "target" in edge_keys
    assert "relation" in edge_keys
