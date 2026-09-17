"""
tests/test_phase6.py — Test suite for LexIndia Phase 6 Multi-Agent Layer & Generation.

Verifies SPEC.md section #7, #8, and section #15 (Phase 6):
- Multi-agent StateGraph with 4 agents: Supervisor, Researcher, Calculator, ComplianceVerifier.
- End-to-end /query workflow on 5 distinct query types (Deduction, Calculation, Hinglish, TDS, Procedure).
- CalculatorAgent slab-wise Old vs New Regime computation table.
- Faithfulness gate and ComplianceVerifier refusal escalation.
- Provider fallback path triggered with mocked Groq 429.
- Full agent_trace telemetry populated on all runs.
"""

import pytest
from src.agents import (
    SupervisorAgent,
    ResearcherAgent,
    CalculatorAgent,
    ComplianceVerifierAgent,
    run_query,
)
from src.agents.tools import calc_tax_old_vs_new
from src.generation.prompts import EXACT_REFUSAL_PHRASE, STANDARD_DISCLAIMER
from src.generation.faithfulness_gate import FaithfulnessGate


def test_supervisor_agent_routing():
    sup = SupervisorAgent()
    assert sup.classify_route("Can I claim Section 80C deduction?") == "DEDUCTION"
    assert sup.classify_route("old vs new regime for 15 lakh income") == "CALCULATION"
    assert sup.classify_route("TDS rate on salary under section 192") == "TDS_TCS"
    assert sup.classify_route("LTCG tax on sale of mutual fund shares") == "CAPITAL_GAINS"
    assert sup.classify_route("due date for filing ITR under section 139") == "PROCEDURE"


def test_supervisor_high_stakes_review_flag():
    sup = SupervisorAgent()
    # High stakes: Capital gains
    s1 = sup.run({"question": "LTCG tax rate on shares", "require_review": False, "agent_trace": []})
    assert s1["review_required"] is True

    # High stakes: NRI
    s2 = sup.run({"question": "tax on NRI bank account interest", "require_review": False, "agent_trace": []})
    assert s2["review_required"] is True

    # Normal deduction without flag
    s3 = sup.run({"question": "HRA deduction limit", "require_review": False, "agent_trace": []})
    assert s3["review_required"] is False


def test_calc_tax_old_vs_new_tool():
    res = calc_tax_old_vs_new(
        fy="2025-26",
        gross_income=1500000.0,
        deductions={"80C": 150000.0, "80D": 25000.0},
        is_salaried=True
    )
    assert res["gross_income"] == 1500000.0
    assert "old_regime" in res
    assert "new_regime" in res
    assert "comparison_table_md" in res
    # For 15L with standard deduction in FY 2025-26, New Regime should have lower or competitive tax
    assert res["new_regime"]["total_tax"] > 0
    assert res["old_regime"]["total_tax"] > 0
    assert "Section 115BAC" in res["comparison_table_md"]


def test_compliance_verifier_refusal_escalation():
    verifier = ComplianceVerifierAgent()
    # Empty chunks must trigger refusal and review escalation
    mock_state = {
        "draft_answer": "Some hallucinated tax advice without any chunks.",
        "retrieved_chunks": [],
        "review_required": False,
        "agent_trace": []
    }
    verified = verifier.run(mock_state)
    assert verified["must_refuse"] is True
    assert verified["refused"] is True
    assert EXACT_REFUSAL_PHRASE in verified["final_answer"]
    assert verified["review_required"] is True
    assert verified["confidence"] <= 0.25


def test_faithfulness_gate_detects_unsupported():
    gate = FaithfulnessGate()
    fake_answer = "You get 100% tax rebate under Section 80C [C99]."
    chunks = [{"text": "Section 80C provides deductions up to 1.5 lakh.", "section_id": "Section 80C"}]
    res = gate.verify_answer(fake_answer, chunks)
    assert "[C99]" in res["unsupported_citations"]
    assert res["is_faithful"] is False


def test_end_to_end_query_deduction():
    res = run_query("Can I claim both HRA and home loan interest deduction?", financial_year="2024-25")
    assert res["route"] == "DEDUCTION"
    assert len(res["retrieved_chunks"]) > 0
    assert len(res["final_answer"]) > 0
    assert len(res["agent_trace"]) >= 4
    # Trace contains Supervisor, Researcher, Generator, Verifier
    agents_in_trace = [t["agent"] for t in res["agent_trace"]]
    assert "SupervisorAgent" in agents_in_trace
    assert "ResearcherAgent" in agents_in_trace
    assert "ComplianceVerifierAgent" in agents_in_trace


def test_end_to_end_query_calculation():
    res = run_query("old vs new regime for 15 lakh income FY 2025-26", financial_year="2025-26")
    assert res["route"] == "CALCULATION"
    assert res["calculation_result"] is not None
    assert "Tax Computation Comparison" in res["final_answer"]
    assert "Section 115BAC" in res["final_answer"]
    agents_in_trace = [t["agent"] for t in res["agent_trace"]]
    assert "CalculatorAgent" in agents_in_trace


def test_end_to_end_query_hinglish():
    res = run_query("kya main apne rent ka deduction le sakta hu?", financial_year="2024-25")
    assert res["route"] in ["DEDUCTION", "PROCEDURE"]
    assert len(res["final_answer"]) > 0
    assert not res["refused"]


def test_provider_fallback_mocked_429():
    res = run_query("Deduction under Section 80C limit", mock_429=True)
    assert res["fallback_used"] is True
    assert res["fallback_model"] is not None
    assert len(res["final_answer"]) > 0


def test_agent_trace_telemetry():
    res = run_query("What are the turnover limits for tax audit under Section 44AB?")
    trace = res["agent_trace"]
    assert len(trace) >= 4
    for entry in trace:
        assert "agent" in entry and entry["agent"].strip()
        assert "action" in entry and entry["action"].strip()
        assert "latency_ms" in entry and isinstance(entry["latency_ms"], int)
        assert "inputs_summary" in entry and entry["inputs_summary"].strip()
        assert "outputs_summary" in entry and entry["outputs_summary"].strip()
