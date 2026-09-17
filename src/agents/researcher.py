"""
src/agents/researcher.py — Researcher Agent for retrieval and citation graph traversal.

Strictly adheres to SPEC.md section #7:
- Uses retrieve_sections to perform hybrid search + cross-encoder reranking (top-8).
- Uses traverse_citation_graph to pull 2-hop neighbors (+4 chunks).
- Populates retrieved_chunks and appends structured entry to agent_trace.
"""

import time
import logging
from typing import Dict, Any

from src.agents.state import LexIndiaState
from src.agents.tools import retrieve_sections, traverse_citation_graph

logger = logging.getLogger("LexIndiaResearcher")


class ResearcherAgent:
    def __init__(self):
        pass

    def run(self, state: LexIndiaState) -> LexIndiaState:
        """Execute statutory research and citation graph traversal."""
        t0 = time.time()
        question = state["question"]
        fy = state.get("financial_year", "2024-25")

        logger.info(f"ResearcherAgent gathering authoritative context for: '{question}' (FY: {fy})")

        # Step 1: Hybrid search + cross-encoder reranker
        top_8 = retrieve_sections(query=question, financial_year=fy)

        # Step 2: 2-hop citation graph traversal
        final_chunks = traverse_citation_graph(top_8)

        latency_ms = int((time.time() - t0) * 1000)

        base_count = sum(1 for c in final_chunks if not c.get("graph_expanded", False))
        graph_count = sum(1 for c in final_chunks if c.get("graph_expanded", False))

        trace_entry = {
            "agent": "ResearcherAgent",
            "action": "Executed hybrid retrieval + 2-hop citation graph expansion",
            "latency_ms": latency_ms,
            "inputs_summary": f"Query: '{question[:60]}...', FY: {fy}",
            "outputs_summary": f"Retrieved {len(final_chunks)} total chunks (Base: {base_count}, Graph-Expanded: {graph_count})"
        }

        new_state = dict(state)
        new_state["retrieved_chunks"] = final_chunks
        new_state.setdefault("agent_trace", []).append(trace_entry)

        return new_state
