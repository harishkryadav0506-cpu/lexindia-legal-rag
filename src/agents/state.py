"""
src/agents/state.py — Typed state definition for LexIndia LangGraph multi-agent system.

Strictly adheres to SPEC.md section #7:
- Defines LexIndiaState with routing, retrieved chunks, computation, citations,
  review flags, refusal flags, provider fallback flags, and full agent_trace telemetry.
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal

RouteType = Literal[
    "DEDUCTION",
    "TDS_TCS",
    "CAPITAL_GAINS",
    "PROCEDURE",
    "CALCULATION",
    "GST",
    "UNKNOWN"
]


class AgentTraceEntry(TypedDict):
    agent: str
    action: str
    latency_ms: int
    inputs_summary: str
    outputs_summary: str


class CitationEntry(TypedDict):
    citation_id: str
    chunk_id: str
    section_id: str
    doc_type: str
    source_url: str
    page_number: int
    score: float
    graph_expanded: bool


class LexIndiaState(TypedDict):
    # User Inputs
    question: str
    financial_year: str
    taxpayer_type: str
    require_review: bool
    mock_429: bool
    thread_id: Optional[str]

    # Routing & Orchestration
    route: RouteType
    review_required: bool
    reviewer_decision: Optional[Dict[str, Any]]

    # Retrieval & Computation Context
    retrieved_chunks: List[Dict[str, Any]]
    calculation_result: Optional[Dict[str, Any]]

    # Generation & Verifications
    draft_answer: str
    final_answer: str
    citations: List[Dict[str, Any]]
    confidence: float
    must_refuse: bool
    refused: bool
    low_confidence: bool

    # Citation Grounding & Verification (Phase 4)
    citation_retry_count: int
    citation_verifier_feedback: Optional[str]
    hallucinated_citations: List[str]
    verified_citations: List[Dict[str, Any]]

    # Fallback & Traceability
    fallback_used: bool
    fallback_model: Optional[str]
    agent_trace: List[AgentTraceEntry]
    total_latency_ms: int

