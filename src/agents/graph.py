"""
src/agents/graph.py — LangGraph StateGraph Orchestration for LexIndia.

Strictly adheres to SPEC.md section #7, #8, and #15 (Phase 6):
- Typed StateGraph(LexIndiaState) with 4 distinct agents:
  1. SupervisorAgent (routing + high-stakes review flagging)
  2. ResearcherAgent (retrieval + 2-hop citation graph traversal)
  3. CalculatorAgent (tax calculation + comparison table)
  4. ComplianceVerifierAgent (faithfulness gate + authority check + refusal escalation)
- Generator node with provider fallback (Groq -> Gemini) and mock_429 support.
- Full agent_trace telemetry returned on every run.
"""

import time
import logging
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, START, END

from src.agents.state import LexIndiaState, AgentTraceEntry
from src.agents.supervisor import SupervisorAgent
from src.agents.researcher import ResearcherAgent
from src.agents.calculator import CalculatorAgent
from src.agents.compliance_verifier import ComplianceVerifierAgent
from src.generation.generator import AnswerGenerator

logger = logging.getLogger("LexIndiaGraph")


def route_decision(state: LexIndiaState) -> str:
    """Conditional edge router based on Supervisor classification."""
    route = state.get("route", "UNKNOWN")
    if route == "CALCULATION":
        return "calculator"
    return "researcher"


class LexIndiaGraphBuilder:
    def __init__(
        self,
        supervisor: Optional[SupervisorAgent] = None,
        researcher: Optional[ResearcherAgent] = None,
        calculator: Optional[CalculatorAgent] = None,
        verifier: Optional[ComplianceVerifierAgent] = None,
        generator: Optional[AnswerGenerator] = None
    ):
        self.supervisor = supervisor or SupervisorAgent()
        self.researcher = researcher or ResearcherAgent()
        self.calculator = calculator or CalculatorAgent()
        self.verifier = verifier or ComplianceVerifierAgent()
        self.generator = generator or AnswerGenerator()

    def supervisor_node(self, state: LexIndiaState) -> LexIndiaState:
        return self.supervisor.run(state)

    def researcher_node(self, state: LexIndiaState) -> LexIndiaState:
        return self.researcher.run(state)

    def calculator_node(self, state: LexIndiaState) -> LexIndiaState:
        return self.calculator.run(state)

    def generator_node(self, state: LexIndiaState) -> LexIndiaState:
        t0 = time.time()
        # If calculator already formed draft answer, pass it forward
        if state.get("route") == "CALCULATION" and state.get("draft_answer"):
            return state

        question = state["question"]
        chunks = state.get("retrieved_chunks", [])
        fy = state.get("financial_year", "2024-25")
        tp = state.get("taxpayer_type", "Individual (Salaried)")
        mock_429 = state.get("mock_429", False)

        gen_res = self.generator.generate_answer(
            question=question,
            chunks=chunks,
            financial_year=fy,
            taxpayer_type=tp,
            mock_429=mock_429
        )

        latency_ms = int((time.time() - t0) * 1000)

        trace_entry: AgentTraceEntry = {
            "agent": "GeneratorAgent",
            "action": f"Synthesized answer (fallback_used={gen_res['fallback_used']})",
            "latency_ms": latency_ms,
            "inputs_summary": f"Question: '{question[:50]}...', Chunks: {len(chunks)}, FY: {fy}",
            "outputs_summary": f"Answer length: {len(gen_res['answer'])}, Refused: {gen_res['refused']}, Fallback: {gen_res['fallback_model']}"
        }

        new_state = dict(state)
        new_state["draft_answer"] = gen_res["answer"]
        new_state["refused"] = gen_res["refused"]
        new_state["fallback_used"] = gen_res["fallback_used"]
        new_state["fallback_model"] = gen_res["fallback_model"]
        new_state["citations"] = gen_res["citations"]
        new_state.setdefault("agent_trace", []).append(trace_entry)

        return new_state

    def verifier_node(self, state: LexIndiaState) -> LexIndiaState:
        return self.verifier.run(state)

    def human_review_node(self, state: LexIndiaState) -> LexIndiaState:
        """
        Human review pass-through node for Phase 6.
        In Phase 7, LangGraph interrupt() is inserted here to pause the graph for reviewer actions.
        """
        # Ensure final_answer is set from draft_answer if not already
        new_state = dict(state)
        if not new_state.get("final_answer"):
            new_state["final_answer"] = new_state.get("draft_answer", "")
        return new_state

    def build(self):
        """Construct and compile the LangGraph StateGraph."""
        builder = StateGraph(LexIndiaState)

        # Add Nodes
        builder.add_node("supervisor", self.supervisor_node)
        builder.add_node("researcher", self.researcher_node)
        builder.add_node("calculator", self.calculator_node)
        builder.add_node("generator", self.generator_node)
        builder.add_node("verifier", self.verifier_node)
        builder.add_node("human_review", self.human_review_node)

        # Add Edges
        builder.add_edge(START, "supervisor")
        builder.add_conditional_edges(
            "supervisor",
            route_decision,
            {
                "calculator": "calculator",
                "researcher": "researcher"
            }
        )
        builder.add_edge("researcher", "generator")
        builder.add_edge("calculator", "generator")
        builder.add_edge("generator", "verifier")
        builder.add_edge("verifier", "human_review")
        builder.add_edge("human_review", END)

        return builder.compile()


# Global graph instance
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        builder = LexIndiaGraphBuilder()
        _compiled_graph = builder.build()
    return _compiled_graph


def run_query(
    question: str,
    financial_year: str = "2024-25",
    taxpayer_type: str = "Individual (Salaried)",
    require_review: bool = False,
    mock_429: bool = False
) -> Dict[str, Any]:
    """
    Execute full multi-agent workflow for a given query.
    Returns structured response dictionary conforming to SPEC API schema.
    """
    t_start = time.time()
    graph = get_graph()

    initial_state: LexIndiaState = {
        "question": question,
        "financial_year": financial_year,
        "taxpayer_type": taxpayer_type,
        "require_review": require_review,
        "mock_429": mock_429,
        "route": "UNKNOWN",
        "review_required": require_review,
        "retrieved_chunks": [],
        "calculation_result": None,
        "draft_answer": "",
        "final_answer": "",
        "citations": [],
        "confidence": 0.0,
        "must_refuse": False,
        "refused": False,
        "low_confidence": False,
        "fallback_used": False,
        "fallback_model": None,
        "agent_trace": [],
        "total_latency_ms": 0
    }

    final_state = graph.invoke(initial_state)
    total_latency = int((time.time() - t_start) * 1000)
    final_state["total_latency_ms"] = total_latency

    return final_state
