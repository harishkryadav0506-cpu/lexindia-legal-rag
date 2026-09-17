"""
LexIndia FastAPI Main Application.
Provides /health check, /query, review queue, and citation graph endpoints.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import time
from src.config import settings, logger

app = FastAPI(
    title="LexIndia Legal RAG API",
    description="Production-grade Legal RAG System for Indian Tax Law Research",
    version="0.1.0",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production can restrict to frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    System health check endpoint verifying:
    - Service uptime
    - Configuration readiness
    - Elasticsearch cluster connectivity
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
        "version": "0.1.0",
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
        },
    }
