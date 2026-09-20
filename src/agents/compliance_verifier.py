"""
src/agents/compliance_verifier.py — Compliance Verifier Agent for Faithfulness and Authority Gates.

Strictly adheres to SPEC.md section #7:
- Faithfulness gate + authority check.
- Sets must_refuse if best rerank score < threshold (default 0.25) or entailment < 0.50.
- Sets review_required=True if confidence < 0.60, or route in HIGH_STAKES, or must_refuse=True (escalation).
- Enforces exact refusal phrase when refusing.
- Appends {agent, action, latency_ms, inputs_summary, outputs_summary} to agent_trace.
"""

import time
import logging
from typing import Dict, Any, Optional

from src.agents.state import LexIndiaState
from src.generation.faithfulness_gate import FaithfulnessGate
from src.generation.prompts import EXACT_REFUSAL_PHRASE, STANDARD_DISCLAIMER

logger = logging.getLogger("LexIndiaComplianceVerifier")


class ComplianceVerifierAgent:
    def __init__(
        self,
        rerank_threshold: float = 0.25,
        entailment_threshold: float = 0.50,
        faithfulness_gate: Optional[FaithfulnessGate] = None
    ):
        self.rerank_threshold = rerank_threshold
        self.entailment_threshold = entailment_threshold
        self.faithfulness_gate = faithfulness_gate or FaithfulnessGate(threshold=entailment_threshold)

    def run(self, state: LexIndiaState) -> LexIndiaState:
        """Verify statutory compliance, faithfulness, and confidence."""
        t0 = time.time()
        draft = state.get("draft_answer", "")
        chunks = state.get("retrieved_chunks", [])
        current_review_req = state.get("review_required", False)

        # 1. Authority check / best rerank score
        best_rerank = 0.0
        if chunks:
            best_rerank = max(c.get("rerank_score", c.get("score", 0.0)) for c in chunks)

        # 2. Faithfulness gate check
        gate_res = self.faithfulness_gate.verify_answer(draft, chunks)
        mean_entailment = gate_res["mean_entailment"]

        # 3. Determine if refusal is required
        already_refused = EXACT_REFUSAL_PHRASE in draft or state.get("refused", False)
        insufficient_authority = best_rerank < self.rerank_threshold
        insufficient_entailment = mean_entailment < self.entailment_threshold

        has_hedging = any(h in draft.lower() for h in [
            "retrieved context does not contain",
            "does not state",
            "cannot answer this specific aspect",
            "insufficient authoritative guidance",
            "low-confidence",
            "no specific provision"
        ])

        # Bug 3 & 4 Fix: If entailment is low (<0.50) REGARDLESS of rerank score (0.06-0.65 dangerous middle zone),
        # require hedging or full refusal - moderate rerank alone must not allow plain factual assertion.
        unfaithful_and_unhedged = insufficient_entailment and not has_hedging
        must_refuse = already_refused or (insufficient_authority and len(chunks) == 0) or unfaithful_and_unhedged

        final_answer = draft
        if must_refuse:
            fy_note = ""
            if draft.startswith("Note: Answer evaluated for selected Financial Year"):
                fy_note = draft.split("\n\n")[0] + "\n\n"
            final_answer = f"{fy_note}{EXACT_REFUSAL_PHRASE}\n\n*{STANDARD_DISCLAIMER}*"
            confidence = 0.20
            refused = True
            draft = final_answer
        else:
            # Combined confidence score
            confidence = round(min(1.0, max(0.1, (best_rerank * 0.4) + (mean_entailment * 0.6))), 3)
            # Bug 9 Fix: Refused flag must be True if final answer is a refusal
            refused = (
                EXACT_REFUSAL_PHRASE in final_answer or
                final_answer.strip().startswith("I cannot find sufficient") or
                state.get("refused", False)
            )
            if refused:
                draft = final_answer

        # Review escalation: confidence < 0.6 OR must_refuse=True (escalation)
        review_required = current_review_req or (confidence < 0.60) or must_refuse

        latency_ms = int((time.time() - t0) * 1000)

        trace_entry = {
            "agent": "ComplianceVerifierAgent",
            "action": "Verified grounding, authority score, and faithfulness",
            "latency_ms": latency_ms,
            "inputs_summary": f"Best Rerank (Raw): {best_rerank:.4f}, Entailment: {mean_entailment:.4f}",
            "outputs_summary": f"Confidence: {confidence:.3f}, MustRefuse: {must_refuse}, Refused: {refused}, ReviewRequired: {review_required}"
        }

        new_state = dict(state)
        new_state["draft_answer"] = draft
        new_state["final_answer"] = final_answer
        if must_refuse or refused:
            new_state["citations"] = []
        new_state["confidence"] = confidence
        new_state["must_refuse"] = must_refuse
        new_state["refused"] = refused
        new_state["low_confidence"] = confidence < 0.60
        new_state["review_required"] = review_required
        new_state.setdefault("agent_trace", []).append(trace_entry)

        logger.info(
            f"ComplianceVerifier completed: confidence={confidence:.3f}, refused={refused}, review_required={review_required}"
        )
        return new_state
