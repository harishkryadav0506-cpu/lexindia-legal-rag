"""
src/agents/supervisor.py — Supervisor Agent for routing, high-stakes triage, and review flagging.

Strictly adheres to SPEC.md section #7:
- Classifies query into: DEDUCTION | TDS_TCS | CAPITAL_GAINS | PROCEDURE | CALCULATION | GST | UNKNOWN.
- Sets review_required flag if:
  * route in HIGH_STAKES = {"CAPITAL_GAINS", "TDS_TCS"}
  * query is NRI-related ("nri" in query)
  * user explicitly sets require_review=True
- Appends {agent, action, latency_ms, inputs_summary, outputs_summary} to agent_trace.
"""

import re
import time
import logging
from typing import Dict, Any

from src.agents.state import LexIndiaState, RouteType

logger = logging.getLogger("LexIndiaSupervisor")

HIGH_STAKES_ROUTES = {"CAPITAL_GAINS", "TDS_TCS"}


class SupervisorAgent:
    def __init__(self):
        pass

    def classify_route(self, question: str) -> RouteType:
        """Classify user question using domain heuristics and pattern matching."""
        q_lower = question.lower()

        # Calculation / slab comparison
        if any(w in q_lower for w in ["old vs new", "calculate", "tax payable", "lakh income", "15 lakh", "10 lakh", "slab rate"]):
            return "CALCULATION"

        # Capital Gains
        if any(w in q_lower for w in ["capital gain", "capital gains", "stcg", "ltcg", "shares sale", "property sale", "section 54", "112a", "111a"]):
            return "CAPITAL_GAINS"

        # TDS / TCS
        if any(w in q_lower for w in ["tds", "tcs", "tax deducted at source", "194", "section 192", "form 16", "form 26as"]):
            return "TDS_TCS"

        # GST
        if any(w in q_lower for w in ["gst", "cgst", "sgst", "igst", "e-way bill", "input tax credit", "itc"]):
            return "GST"

        # Deductions & Exemptions
        if any(w in q_lower for w in ["deduction", "deduct", "80c", "80d", "hra", "rent", "kiraya", "home loan", "interest", "exemption", "10(13a)", "24(b)", "claim"]):
            return "DEDUCTION"

        # Procedures & Filing
        if any(w in q_lower for w in ["itr", "return", "filing", "due date", "audit", "44ab", "belated", "revised", "penalty", "notice", "139"]):
            return "PROCEDURE"

        return "UNKNOWN"

    def run(self, state: LexIndiaState) -> LexIndiaState:
        """Execute supervisor routing step."""
        t0 = time.time()
        question = state["question"]
        route = self.classify_route(question)

        # Check high-stakes conditions
        is_nri = "nri" in question.lower() or "non-resident" in question.lower() or "non resident" in question.lower()
        explicit_review = state.get("require_review", False)
        is_high_stakes = route in HIGH_STAKES_ROUTES or is_nri or explicit_review

        latency_ms = int((time.time() - t0) * 1000)

        # Build trace entry
        trace_entry = {
            "agent": "SupervisorAgent",
            "action": f"Classified query into route: {route}",
            "latency_ms": latency_ms,
            "inputs_summary": f"Question: '{question[:60]}...', require_review: {explicit_review}",
            "outputs_summary": f"Route: {route}, review_required: {is_high_stakes} (nri={is_nri})"
        }

        # Update state
        new_state = dict(state)
        new_state["route"] = route
        new_state["review_required"] = is_high_stakes
        new_state.setdefault("agent_trace", []).append(trace_entry)

        logger.info(f"Supervisor routed to {route} | review_required={is_high_stakes}")
        return new_state
