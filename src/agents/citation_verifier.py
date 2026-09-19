"""
src/agents/citation_verifier.py — Citation Verifier Node for Strict Grounding.

Strictly fulfills Phase 4 requirements:
1. Parses all [C1], [C2], etc. citation tags from draft_answer.
2. Cross-references tags against retrieved chunks (valid range: 1..len(chunks)).
3. If hallucinated citations are detected:
   - Increments citation_retry_count.
   - If retry_count < 2: sets prompt correction feedback:
     "You cited [C5] which is not in context. Rewrite using only C1-C{N}."
     and triggers RetryGeneration back to generator node.
   - If retry_count >= 2: escalates to Human-in-the-Loop review (review_required=True)
     which pauses via LangGraph interrupt().
4. If citations are valid: maps chunks to citation metadata and passes to ComplianceVerifier.
"""

import re
import time
import logging
from typing import Dict, Any, List, Set

from src.agents.state import LexIndiaState, AgentTraceEntry

logger = logging.getLogger("LexIndiaCitationVerifier")


class CitationVerifierAgent:
    def __init__(self):
        pass

    def run(self, state: LexIndiaState) -> LexIndiaState:
        """Verify that all citation tags in draft_answer correspond to real retrieved chunks."""
        t0 = time.time()
        draft = state.get("draft_answer", "")
        chunks = state.get("retrieved_chunks", [])
        num_chunks = len(chunks)
        retry_count = state.get("citation_retry_count", 0)

        # 1. Parse all [C#] tags
        cited_indices_raw = re.findall(r'\[C(\d+)\]', draft)
        cited_indices = [int(idx) for idx in cited_indices_raw]

        hallucinated_tags = []
        valid_tags = []

        if num_chunks == 0:
            if cited_indices:
                hallucinated_tags = [f"[C{i}]" for i in sorted(set(cited_indices))]
        else:
            for idx in cited_indices:
                tag = f"[C{idx}]"
                if 1 <= idx <= num_chunks:
                    if tag not in valid_tags:
                        valid_tags.append(tag)
                else:
                    if tag not in hallucinated_tags:
                        hallucinated_tags.append(tag)

        # 2. Check if verification passed or failed
        new_state = dict(state)
        new_state["hallucinated_citations"] = hallucinated_tags

        if hallucinated_tags:
            retry_count += 1
            new_state["citation_retry_count"] = retry_count
            bad_tags_str = ", ".join(hallucinated_tags)

            if retry_count < 2:
                # Trigger retry with corrective feedback
                feedback = (
                    f"You cited {bad_tags_str} which is not in context. "
                    f"Rewrite using only C1-C{num_chunks}."
                )
                new_state["citation_verifier_feedback"] = feedback
                action_msg = f"Citation hallucination detected ({bad_tags_str}); triggering retry #{retry_count}"
                logger.warning(f"CitationVerifier: {action_msg}")
            else:
                # Escalation to Human Review after 2 failed verification attempts
                feedback = (
                    f"Citation verification failed twice ({bad_tags_str} not in context). "
                    f"Escalating to human review."
                )
                new_state["citation_verifier_feedback"] = feedback
                new_state["review_required"] = True
                action_msg = f"Citation verification failed twice ({bad_tags_str}); escalated to HITL review"
                logger.error(f"CitationVerifier: {action_msg}")

            trace_entry: AgentTraceEntry = {
                "agent": "CitationVerifierAgent",
                "action": action_msg,
                "latency_ms": int((time.time() - t0) * 1000),
                "inputs_summary": f"Draft citations: {sorted(set(f'[C{i}]' for i in cited_indices))}, Chunks: {num_chunks}",
                "outputs_summary": f"Hallucinated: {hallucinated_tags}, RetryCount: {retry_count}, ReviewRequired: {new_state.get('review_required', False)}"
            }
            new_state.setdefault("agent_trace", []).append(trace_entry)
            return new_state

        # All citations valid (or no citations if refusal/empty)
        new_state["citation_verifier_feedback"] = None
        verified_meta = []
        for idx in sorted(set(cited_indices)):
            c = chunks[idx - 1]
            verified_meta.append({
                "citation_id": f"[C{idx}]",
                "chunk_id": c.get("chunk_id"),
                "section_id": c.get("section_id"),
                "doc_type": c.get("doc_type"),
                "source_url": c.get("source_url"),
                "page_number": c.get("page_number"),
                "score": c.get("final_score", c.get("rerank_score", 0.0)),
                "graph_expanded": c.get("graph_expanded", False)
            })

        new_state["verified_citations"] = verified_meta
        if verified_meta:
            new_state["citations"] = verified_meta

        trace_entry: AgentTraceEntry = {
            "agent": "CitationVerifierAgent",
            "action": f"Verified {len(valid_tags)} grounded citations",
            "latency_ms": int((time.time() - t0) * 1000),
            "inputs_summary": f"Draft citations: {valid_tags}, Chunks: {num_chunks}",
            "outputs_summary": f"Verified {len(verified_meta)} chunk mappings. Zero hallucinations."
        }
        new_state.setdefault("agent_trace", []).append(trace_entry)
        logger.info(f"CitationVerifier: Successfully validated {len(verified_meta)} citations: {valid_tags}")
        return new_state
