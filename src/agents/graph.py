"""
src/agents/graph.py — LangGraph StateGraph Orchestration for LexIndia.

Strictly adheres to SPEC.md section #7, #8, #9, and #15 (Phase 7):
- Typed StateGraph(LexIndiaState) with 4 distinct agents:
  1. SupervisorAgent (routing + high-stakes review flagging)
  2. ResearcherAgent (retrieval + 2-hop citation graph traversal)
  3. CalculatorAgent (tax calculation + comparison table)
  4. ComplianceVerifierAgent (faithfulness gate + authority check + refusal escalation)
- Human Review Node with LangGraph interrupt() + SqliteSaver checkpointing:
  * Triggers when review_required=True (confidence < 0.6, high-stakes, refusal escalation, or require_review flag)
  * Pauses exposing thread_id, draft_answer, citations, route, confidence
  * Resumes on Command(resume=decision) with approve | edit | reject
  * Records decision in review_store (SQLite reviews table)
  * Appends verified pairs to human_verified_pairs.json on approve/edit
- Generator node with provider fallback (Groq -> Gemini) and mock_429 support.
- Full agent_trace telemetry returned on every run.
"""

import time
import uuid
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver

from src.config import settings
from src.agents.state import LexIndiaState, AgentTraceEntry
from src.agents.supervisor import SupervisorAgent
from src.agents.researcher import ResearcherAgent
from src.agents.calculator import CalculatorAgent
from src.agents.compliance_verifier import ComplianceVerifierAgent
from src.agents.citation_verifier import CitationVerifierAgent
from src.agents.review_store import review_store
from src.generation.generator import AnswerGenerator
from src.generation.prompts import EXACT_REFUSAL_PHRASE, STANDARD_DISCLAIMER

logger = logging.getLogger("LexIndiaGraph")


def route_decision(state: LexIndiaState) -> str:
    """Conditional edge router based on Supervisor classification."""
    route = state.get("route", "UNKNOWN")
    if route == "CALCULATION":
        return "calculator"
    return "researcher"


def route_citation_verifier(state: LexIndiaState) -> str:
    """
    Conditional edge router after CitationVerifierAgent:
    - If hallucinated citation tags found and retry_count < 2: return "generator" (RetryGeneration).
    - If hallucinated citation tags found and retry_count >= 2: return "human_review" (escalate to HITL).
    - If all citations valid: return "verifier" (pass to ComplianceVerifier).
    """
    hallucinated = state.get("hallucinated_citations", [])
    if hallucinated:
        retry_count = state.get("citation_retry_count", 0)
        if retry_count < 2:
            return "generator"
        return "human_review"
    return "verifier"


class LexIndiaGraphBuilder:
    def __init__(
        self,
        supervisor: Optional[SupervisorAgent] = None,
        researcher: Optional[ResearcherAgent] = None,
        calculator: Optional[CalculatorAgent] = None,
        verifier: Optional[ComplianceVerifierAgent] = None,
        citation_verifier: Optional[CitationVerifierAgent] = None,
        generator: Optional[AnswerGenerator] = None,
        checkpoints_db_path: Optional[Path] = None
    ):
        self.supervisor = supervisor or SupervisorAgent()
        self.researcher = researcher or ResearcherAgent()
        self.calculator = calculator or CalculatorAgent()
        self.verifier = verifier or ComplianceVerifierAgent()
        self.citation_verifier = citation_verifier or CitationVerifierAgent()
        self.generator = generator or AnswerGenerator()
        self.checkpoints_db_path = checkpoints_db_path or settings.CHECKPOINTS_DB_PATH
        self.checkpoints_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.checkpoints_db_path), check_same_thread=False)
        self.checkpointer = SqliteSaver(self._conn)

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
        feedback = state.get("citation_verifier_feedback")

        gen_res = self.generator.generate_answer(
            question=question,
            chunks=chunks,
            financial_year=fy,
            taxpayer_type=tp,
            mock_429=mock_429,
            feedback=feedback
        )

        latency_ms = int((time.time() - t0) * 1000)

        trace_entry: AgentTraceEntry = {
            "agent": "GeneratorAgent",
            "action": f"Synthesized answer (fallback_used={gen_res['fallback_used']}, retry_feedback={'Yes' if feedback else 'None'})",
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

    def citation_verifier_node(self, state: LexIndiaState) -> LexIndiaState:
        return self.citation_verifier.run(state)

    def verifier_node(self, state: LexIndiaState) -> LexIndiaState:
        return self.verifier.run(state)

    def human_review_node(self, state: LexIndiaState) -> LexIndiaState:
        """
        Human-in-the-loop review node.
        If review_required=True, triggers LangGraph interrupt() and saves state to checkpoints.
        On resume, receives Command(resume=decision) to apply approve | edit | reject.
        """
        new_state = dict(state)
        thread_id = new_state.get("thread_id") or f"thread_{uuid.uuid4().hex[:12]}"
        new_state["thread_id"] = thread_id

        # Determine if human review is required
        needs_review = new_state.get("review_required", False)

        if needs_review:
            logger.info(f"Human review triggered for thread_id={thread_id}")
            # 1. Record pending review entry in SQLite review store
            review_store.create_review_entry(
                thread_id=thread_id,
                query=new_state.get("question", ""),
                financial_year=new_state.get("financial_year", "2024-25"),
                taxpayer_type=new_state.get("taxpayer_type", "Individual (Salaried)"),
                draft_answer=new_state.get("draft_answer", ""),
                citations=new_state.get("citations", []),
                agent_trace=new_state.get("agent_trace", []),
                route=new_state.get("route", "UNKNOWN"),
                confidence=new_state.get("confidence", 0.0),
                action="pending"
            )

            # 2. Pause graph via interrupt()
            interrupt_payload = {
                "thread_id": thread_id,
                "status": "awaiting_review",
                "draft_answer": new_state.get("draft_answer", ""),
                "citations": new_state.get("citations", []),
                "route": new_state.get("route", "UNKNOWN"),
                "confidence": new_state.get("confidence", 0.0),
                "review_required": True
            }

            # This call will pause graph execution until resumed with Command(resume=decision)
            decision = interrupt(interrupt_payload)

            # 3. Graph resumed with decision
            t0 = time.time()
            action = decision.get("action", "approve") if isinstance(decision, dict) else "approve"
            edited_answer = decision.get("edited_answer") if isinstance(decision, dict) else None
            reviewer_note = decision.get("reviewer_note") if isinstance(decision, dict) else None

            if action == "edit" and edited_answer:
                final_answer = edited_answer
                refused = False
            elif action == "reject":
                refused = True
                note_suffix = f"\n\nReviewer note: {reviewer_note}" if reviewer_note else ""
                final_answer = f"{EXACT_REFUSAL_PHRASE}{note_suffix}\n\n*{STANDARD_DISCLAIMER}*"
            else:  # approve
                final_answer = new_state.get("draft_answer", "")
                refused = new_state.get("refused", False)

            # 4. Record decision in review store and append verified pairs if approved/edited
            review_store.record_decision(
                thread_id=thread_id,
                action=action,
                final_answer=final_answer,
                reviewer_note=reviewer_note
            )

            latency_ms = int((time.time() - t0) * 1000)
            trace_entry: AgentTraceEntry = {
                "agent": "HumanReviewNode",
                "action": f"Human review decision applied ({action})",
                "latency_ms": latency_ms,
                "inputs_summary": f"Action: {action}, Reviewer Note: {reviewer_note or 'None'}",
                "outputs_summary": f"Final answer updated (len={len(final_answer)}), Refused={refused}"
            }

            new_state["final_answer"] = final_answer
            new_state["refused"] = refused
            new_state["review_required"] = False
            new_state["reviewer_decision"] = decision
            new_state.setdefault("agent_trace", []).append(trace_entry)
            logger.info(f"Human review completed for thread_id={thread_id} with action={action}")
        else:
            # Direct pass-through if no review required
            if not new_state.get("final_answer"):
                new_state["final_answer"] = new_state.get("draft_answer", "")

        return new_state

    def build(self):
        """Construct and compile the LangGraph StateGraph with checkpointer."""
        builder = StateGraph(LexIndiaState)

        # Add Nodes
        builder.add_node("supervisor", self.supervisor_node)
        builder.add_node("researcher", self.researcher_node)
        builder.add_node("calculator", self.calculator_node)
        builder.add_node("generator", self.generator_node)
        builder.add_node("citation_verifier", self.citation_verifier_node)
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
        builder.add_edge("generator", "citation_verifier")
        builder.add_conditional_edges(
            "citation_verifier",
            route_citation_verifier,
            {
                "generator": "generator",
                "human_review": "human_review",
                "verifier": "verifier"
            }
        )
        builder.add_edge("verifier", "human_review")
        builder.add_edge("human_review", END)

        return builder.compile(checkpointer=self.checkpointer)


# Global graph instance
_graph_builder = None
_compiled_graph = None


def get_graph():
    global _graph_builder, _compiled_graph
    if _compiled_graph is None:
        _graph_builder = LexIndiaGraphBuilder()
        _compiled_graph = _graph_builder.build()
    return _compiled_graph


def run_query(
    question: str,
    financial_year: str = "2024-25",
    taxpayer_type: str = "Individual (Salaried)",
    require_review: bool = False,
    mock_429: bool = False,
    thread_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute full multi-agent workflow for a given query.
    If review is triggered, graph pauses at human_review node and returns awaiting_review status.
    Otherwise, returns complete status with final answer and citations.
    """
    t_start = time.time()
    graph = get_graph()

    tid = thread_id or f"thread_{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": tid}}

    initial_state: LexIndiaState = {
        "question": question,
        "financial_year": financial_year,
        "taxpayer_type": taxpayer_type,
        "require_review": require_review,
        "mock_429": mock_429,
        "thread_id": tid,
        "route": "UNKNOWN",
        "review_required": require_review,
        "reviewer_decision": None,
        "retrieved_chunks": [],
        "calculation_result": None,
        "draft_answer": "",
        "final_answer": "",
        "citations": [],
        "confidence": 0.0,
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

    run_result = graph.invoke(initial_state, config=config)
    total_latency = int((time.time() - t_start) * 1000)

    # Check if the graph was paused by interrupt()
    is_interrupted = bool(run_result.get("__interrupt__"))

    if is_interrupted:
        draft = run_result.get("draft_answer", "")
        refused = bool(
            run_result.get("refused", False) or
            (draft and (EXACT_REFUSAL_PHRASE in draft or draft.strip().startswith("I cannot find sufficient")))
        )
        return {
            "status": "awaiting_review",
            "thread_id": tid,
            "draft_answer": draft,
            "final_answer": draft,  # provided for test compatibility
            "citations": run_result.get("citations", []),
            "confidence": run_result.get("confidence", 0.0),
            "route": run_result.get("route", "UNKNOWN"),
            "refused": refused,
            "retrieved_chunks": run_result.get("retrieved_chunks", []),
            "calculation_result": run_result.get("calculation_result"),
            "review_required": True,
            "fallback_used": run_result.get("fallback_used", False),
            "fallback_model": run_result.get("fallback_model"),
            "agent_trace": run_result.get("agent_trace", []),
            "total_latency_ms": total_latency
        }
    else:
        answer = run_result.get("final_answer") or run_result.get("draft_answer", "")
        refused = bool(
            run_result.get("refused", False) or
            (answer and (EXACT_REFUSAL_PHRASE in answer or answer.strip().startswith("I cannot find sufficient")))
        )
        return {
            "status": "complete",
            "thread_id": tid,
            "answer": answer,
            "final_answer": answer,
            "draft_answer": run_result.get("draft_answer", ""),
            "citations": run_result.get("citations", []),
            "confidence": run_result.get("confidence", 0.0),
            "refused": refused,
            "route": run_result.get("route", "UNKNOWN"),
            "retrieved_chunks": run_result.get("retrieved_chunks", []),
            "calculation_result": run_result.get("calculation_result"),
            "review_required": False,
            "fallback_used": run_result.get("fallback_used", False),
            "fallback_model": run_result.get("fallback_model"),
            "agent_trace": run_result.get("agent_trace", []),
            "total_latency_ms": total_latency
        }


def resume_query_review(
    thread_id: str,
    action: str,
    edited_answer: Optional[str] = None,
    reviewer_note: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resume an interrupted review graph using Command(resume=decision).
    Returns the final response object conforming to SPEC.md section #9.
    """
    t0 = time.time()
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    decision = {
        "action": action,
        "edited_answer": edited_answer,
        "reviewer_note": reviewer_note or ""
    }

    final_state = graph.invoke(Command(resume=decision), config=config)
    total_latency = int((time.time() - t0) * 1000)

    final_ans = final_state.get("final_answer", "")
    return {
        "status": "complete",
        "thread_id": thread_id,
        "action": action,
        "answer": final_ans,
        "final_answer": final_ans,
        "draft_answer": final_state.get("draft_answer", ""),
        "citations": final_state.get("citations", []),
        "confidence": final_state.get("confidence", 0.0),
        "refused": bool(
            final_state.get("refused", False) or
            (final_ans and (EXACT_REFUSAL_PHRASE in final_ans or final_ans.strip().startswith("I cannot find sufficient")))
        ),
        "route": final_state.get("route", "UNKNOWN"),
        "retrieved_chunks": final_state.get("retrieved_chunks", []),
        "calculation_result": final_state.get("calculation_result"),
        "review_required": False,
        "fallback_used": final_state.get("fallback_used", False),
        "fallback_model": final_state.get("fallback_model"),
        "agent_trace": final_state.get("agent_trace", []),
        "reviewer_note": reviewer_note or "",
        "latency_ms": total_latency,
        "total_latency_ms": total_latency
    }
