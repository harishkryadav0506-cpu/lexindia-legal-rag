"""
src/api/schemas.py — Pydantic schemas for LexIndia FastAPI endpoints.

Strictly adheres to SPEC.md section #9:
- Request and Response schemas for /query, /reviews/{thread_id}/decision,
  /reviews/pending, /reviews/stats, and /graph.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., description="Tax law question or user query", min_length=2)
    financial_year: Optional[str] = Field(default="2024-25", description="Assessment/Financial Year context (e.g. '2024-25')")
    taxpayer_type: Optional[str] = Field(default="Individual (Salaried)", description="Taxpayer classification category")
    require_review: Optional[bool] = Field(default=False, description="Flag to force expert human-in-the-loop review")
    mock_429: Optional[bool] = Field(default=False, description="Testing flag to simulate provider 429 rate limit")


class CitationItem(BaseModel):
    chunk_id: Optional[str] = None
    section_id: Optional[str] = None
    doc_type: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    score: Optional[float] = None
    graph_expanded: Optional[bool] = False


class AgentTraceItem(BaseModel):
    agent: str
    action: str
    latency_ms: int
    inputs_summary: str
    outputs_summary: str


class QueryResponse(BaseModel):
    status: Literal["complete", "awaiting_review"]
    thread_id: Optional[str] = None
    answer: Optional[str] = None
    draft_answer: Optional[str] = None
    final_answer: Optional[str] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[float] = 0.0
    refused: Optional[bool] = False
    route: Optional[str] = "UNKNOWN"
    latency_ms: Optional[int] = 0
    fallback_used: Optional[bool] = False
    fallback_model: Optional[str] = None
    agent_trace: List[Dict[str, Any]] = Field(default_factory=list)
    review_required: Optional[bool] = False


class ReviewDecisionRequest(BaseModel):
    action: Literal["approve", "edit", "reject"] = Field(..., description="Review action to take")
    edited_answer: Optional[str] = Field(default=None, description="Corrected or modified text if action is edit")
    reviewer_note: Optional[str] = Field(default=None, description="Optional note or rationale by reviewer")


class ReviewPendingItem(BaseModel):
    id: Optional[int] = None
    thread_id: str
    query: str
    financial_year: Optional[str] = None
    taxpayer_type: Optional[str] = None
    draft_answer: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    route: Optional[str] = None
    confidence: Optional[float] = None
    age_minutes: float = 0.0
    created_at: Optional[str] = None


class ReviewStatsResponse(BaseModel):
    approval_rate: float
    edit_rate: float
    reject_rate: float
    avg_normalized_edit_distance: float
    review_trigger_rate: float
    total_reviews: int
    total_decided: int
    pending_count: int


class GraphNode(BaseModel):
    id: str
    label: str
    authority_level: int
    doc_type: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    source_doc: Optional[str] = None


class GraphResponse(BaseModel):
    section_id: str
    hops: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]
