"""
LexIndia FastAPI Main Application.

Strictly adheres to SPEC.md section #9:
- POST /query: Executes multi-agent RAG workflow, triggers HITL if review_required.
- POST /reviews/{thread_id}/decision: Resumes paused review graph via Command(resume=decision).
- GET /reviews/pending: Queue list of pending human reviews with age in minutes.
- GET /reviews/stats: Metrics (approval_rate, edit_rate, reject_rate, avg_normalized_edit_distance, review_trigger_rate).
- GET /graph: Subgraph extraction for section visualization.
- GET /health: Health check verifying ES cluster and SQLite databases.
- In-memory rate limiting (30 req/min) and CORS middleware.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

from fastapi import FastAPI, Request, Query, Path, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

from src.config import settings, logger
from src.agents.graph import run_query, resume_query_review
from src.agents.review_store import review_store
from src.retrieval.citation_graph import CitationGraph
from src.api.schemas import (
    QueryRequest,
    QueryResponse,
    ReviewDecisionRequest,
    ReviewPendingItem,
    ReviewStatsResponse,
    GraphResponse,
)

app = FastAPI(
    title="LexIndia Legal RAG API",
    description="Production-grade Legal RAG System for Indian Tax Law Research with Human-in-the-Loop",
    version="0.2.0",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory sliding window rate limiter (30 req/minute per IP)
CALL_HISTORY = defaultdict(list)
RATE_LIMIT = settings.RATE_LIMIT_PER_MINUTE
WINDOW_SECONDS = 60


def enforce_rate_limit(request: Request):
    """Enforce 30 requests per minute sliding window per client IP."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    cutoff = now - WINDOW_SECONDS
    CALL_HISTORY[client_ip] = [t for t in CALL_HISTORY[client_ip] if t > cutoff]
    if len(CALL_HISTORY[client_ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: maximum {RATE_LIMIT} requests per minute allowed."
        )
    CALL_HISTORY[client_ip].append(now)


# Citation graph singleton cache
_citation_graph = None


def get_citation_graph() -> CitationGraph:
    global _citation_graph
    if _citation_graph is None:
        _citation_graph = CitationGraph()
    return _citation_graph


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    System health check endpoint verifying:
    - Service uptime
    - Configuration readiness
    - Elasticsearch cluster connectivity
    - Review store and checkpoints database status
    """
    es_status = "unreachable"
    es_cluster_name = None
    es_version = None

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(settings.ES_URL)
            if resp.status_code == 200:
                data = resp.json()
                es_status = "connected"
                es_cluster_name = data.get("cluster_name")
                es_version = data.get("version", {}).get("number")
    except Exception as exc:
        logger.warning(f"Elasticsearch health check failed: {exc}")
        es_status = f"disconnected: {str(exc)}"

    return {
        "status": "healthy",
        "service": "LexIndia Legal RAG API",
        "version": "0.2.0",
        "timestamp": time.time(),
        "config": {
            "llm_provider": settings.LLM_PROVIDER,
            "generation_model": settings.GENERATION_MODEL,
            "expansion_model": settings.EXPANSION_MODEL,
            "judge_primary": settings.JUDGE_PRIMARY,
            "es_url": settings.ES_URL,
            "es_index": settings.ES_INDEX,
            "enable_gst": settings.ENABLE_GST,
        },
        "components": {
            "elasticsearch": {
                "status": es_status,
                "cluster_name": es_cluster_name,
                "version": es_version,
            },
            "reviews_db": {
                "path": str(settings.REVIEWS_DB_PATH),
                "exists": settings.REVIEWS_DB_PATH.exists(),
            },
            "checkpoints_db": {
                "path": str(settings.CHECKPOINTS_DB_PATH),
                "exists": settings.CHECKPOINTS_DB_PATH.exists(),
            },
        },
    }


@app.post("/query", response_model=QueryResponse, status_code=status.HTTP_200_OK)
def query_endpoint(req: QueryRequest, request: Request):
    """
    Execute full multi-agent legal RAG query.
    If human review is required, returns status="awaiting_review" with thread_id and draft_answer.
    Otherwise, returns status="complete" with cited final answer.
    """
    enforce_rate_limit(request)

    res = run_query(
        question=req.question,
        financial_year=req.financial_year or "2024-25",
        taxpayer_type=req.taxpayer_type or "Individual (Salaried)",
        require_review=bool(req.require_review),
        mock_429=bool(req.mock_429)
    )

    return QueryResponse(
        status=res.get("status", "complete"),
        thread_id=res.get("thread_id"),
        answer=res.get("answer") or res.get("final_answer"),
        draft_answer=res.get("draft_answer"),
        final_answer=res.get("final_answer"),
        citations=res.get("citations", []),
        confidence=res.get("confidence", 0.0),
        refused=res.get("refused", False),
        route=res.get("route", "UNKNOWN"),
        latency_ms=res.get("total_latency_ms", 0),
        fallback_used=res.get("fallback_used", False),
        fallback_model=res.get("fallback_model"),
        agent_trace=res.get("agent_trace", []),
        review_required=res.get("review_required", False)
    )


@app.post("/reviews/{thread_id}/decision", response_model=QueryResponse, status_code=status.HTTP_200_OK)
def review_decision_endpoint(
    thread_id: str = Path(..., description="Thread ID of the paused review"),
    decision_req: ReviewDecisionRequest = None,
    request: Request = None
):
    """
    Submit reviewer decision ('approve', 'edit', 'reject') for a paused query.
    Resumes LangGraph execution and returns final answer response.
    """
    if request:
        enforce_rate_limit(request)

    try:
        res = resume_query_review(
            thread_id=thread_id,
            action=decision_req.action,
            edited_answer=decision_req.edited_answer,
            reviewer_note=decision_req.reviewer_note
        )
    except Exception as e:
        logger.error(f"Error resuming review for thread_id={thread_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to resume review for thread {thread_id}: {str(e)}"
        )

    return QueryResponse(
        status="complete",
        thread_id=thread_id,
        answer=res.get("final_answer"),
        draft_answer=res.get("draft_answer"),
        final_answer=res.get("final_answer"),
        citations=res.get("citations", []),
        confidence=res.get("confidence", 0.0),
        refused=res.get("refused", False),
        route=res.get("route", "UNKNOWN"),
        latency_ms=res.get("latency_ms", 0),
        fallback_used=res.get("fallback_used", False),
        fallback_model=res.get("fallback_model"),
        agent_trace=res.get("agent_trace", []),
        review_required=False
    )


@app.get("/reviews/pending", response_model=List[ReviewPendingItem], status_code=status.HTTP_200_OK)
def get_pending_reviews_endpoint():
    """Retrieve queue of pending human reviews ordered by age."""
    pending = review_store.get_pending_reviews()
    items = []
    for p in pending:
        items.append(ReviewPendingItem(
            id=p.get("id"),
            thread_id=p.get("thread_id"),
            query=p.get("query"),
            financial_year=p.get("financial_year"),
            taxpayer_type=p.get("taxpayer_type"),
            draft_answer=p.get("draft_answer", ""),
            citations=p.get("citations", []),
            route=p.get("route"),
            confidence=p.get("confidence"),
            age_minutes=p.get("age_minutes", 0.0),
            created_at=p.get("created_at")
        ))
    return items


@app.get("/reviews/stats", response_model=ReviewStatsResponse, status_code=status.HTTP_200_OK)
def get_review_stats_endpoint():
    """Retrieve aggregate human-in-the-loop review statistics."""
    stats = review_store.get_review_stats()
    return ReviewStatsResponse(**stats)


@app.get("/graph", response_model=GraphResponse, status_code=status.HTTP_200_OK)
def get_citation_subgraph(
    section_id: str = Query(..., description="Target section ID (e.g. 'Section 80C' or 'Section 10(13A)')"),
    hops: int = Query(default=2, ge=1, le=4, description="Number of traversal hops (1 to 4)")
):
    """Extract an ego subgraph centered at section_id for visual graph rendering."""
    cg = get_citation_graph()
    subgraph = cg.get_subgraph(section_id=section_id, hops=hops)
    return GraphResponse(
        section_id=section_id,
        hops=hops,
        nodes=subgraph.get("nodes", []),
        edges=subgraph.get("edges", [])
    )
