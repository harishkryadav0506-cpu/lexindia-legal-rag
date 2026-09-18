"""
Tests for Phase 1: Repo scaffold, configuration, and /health check endpoint.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from src.config import settings
from src.api.main import app


def test_settings_roles_and_defaults():
    """Verify model roles and configuration defaults per SPEC."""
    assert settings.LLM_PROVIDER in ["groq", "together", "hf"]
    assert settings.GENERATION_MODEL is not None
    assert settings.EXPANSION_MODEL is not None
    assert settings.JUDGE_PRIMARY in ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]
    assert settings.JUDGE_SECONDARY == settings.GENERATION_MODEL
    assert settings.ES_INDEX in ["lexindia_corpus", "lexindia-v2"]
    assert settings.RATE_LIMIT_PER_MINUTE == 30


@pytest.mark.asyncio
async def test_health_endpoint_contract():
    """Verify /health endpoint returns expected schema and connects to ES."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["service"] == "LexIndia Legal RAG API"
    assert "config" in data
    assert "components" in data
    
    # Elasticsearch component check
    es_comp = data["components"]["elasticsearch"]
    assert es_comp["status"] == "connected"
    assert es_comp["version"] == "8.13.0"
