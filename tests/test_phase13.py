"""
tests/test_phase13.py — Automated Unit Tests for Packaging, Licensing & Documentation (Phase 13).

Tests:
1. MIT License existence and copyright assertion.
2. Root and modular Dockerfile integrity and directives.
3. Elasticsearch init script and supervisor configuration.
4. README.md completeness and architectural documentation.
5. Verification of overall repository compliance against SPEC.md.
"""

from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_license_file():
    """Verify MIT License with Copyright (c) 2026 Harish Yadav."""
    license_path = REPO_ROOT / "LICENSE"
    assert license_path.exists(), "LICENSE file must exist in repo root"

    content = license_path.read_text(encoding="utf-8")
    assert "MIT License" in content
    assert "Copyright (c) 2026 Harish Yadav" in content


def test_dockerfiles_and_packaging_artifacts():
    """Verify Dockerfile, frontend/Dockerfile, docker/Dockerfile, and compose files."""
    root_dockerfile = REPO_ROOT / "Dockerfile"
    backend_dockerfile = REPO_ROOT / "docker" / "Dockerfile"
    frontend_dockerfile = REPO_ROOT / "frontend" / "Dockerfile"
    docker_compose = REPO_ROOT / "docker-compose.yml"
    es_init = REPO_ROOT / "docker" / "es_init.sh"
    supervisord_conf = REPO_ROOT / "docker" / "supervisord.conf"

    assert root_dockerfile.exists(), "Root Dockerfile must exist for HF Spaces/containerization"
    assert backend_dockerfile.exists(), "docker/Dockerfile must exist for backend service"
    assert frontend_dockerfile.exists(), "frontend/Dockerfile must exist for Next.js service"
    assert docker_compose.exists(), "docker-compose.yml must exist in root"
    assert es_init.exists(), "docker/es_init.sh must exist"
    assert supervisord_conf.exists(), "docker/supervisord.conf must exist"

    # Verify root Dockerfile exposes 7860 (Hugging Face default)
    root_df_text = root_dockerfile.read_text(encoding="utf-8")
    assert "EXPOSE 7860" in root_df_text
    assert "supervisord" in root_df_text

    # Verify es_init script has curl and health check
    es_init_text = es_init.read_text(encoding="utf-8")
    assert "lexindia_corpus" in es_init_text


def test_readme_documentation_completeness():
    """Verify README.md contains all essential production sections."""
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.exists(), "README.md must exist in repo root"

    content = readme_path.read_text(encoding="utf-8")
    assert "# LexIndia — Legal RAG System for Indian Tax Law Research" in content
    assert "System Architecture Overview" in content
    assert "mermaid" in content
    assert "Model Cards & LLM Role Configuration" in content
    assert "Real Government Legal Corpus" in content
    assert "Model Context Protocol (FastMCP Server)" in content
    assert "Human-in-the-Loop (HITL) Review System" in content
    assert "Benchmark Evaluation Results (100 Real Queries)" in content
    assert "Generation Model Ablation Study" in content
    assert "Quickstart & Installation" in content
    assert "Future Work & Production Roadmap" in content
    assert "License & Attribution" in content
    assert "Copyright (c) 2026 Harish Yadav" in content


def test_full_project_spec_compliance_checklist():
    """Verify all key architectural files mandated across SPEC.md exist."""
    critical_files = [
        REPO_ROOT / "DATA_SOURCES.md",
        REPO_ROOT / "EVALUATION_REPORT.md",
        REPO_ROOT / "ABLATION_TABLE.md",
        REPO_ROOT / "DATA_AUDIT.md",
        REPO_ROOT / "PROGRESS.md",
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / ".env.example",
        REPO_ROOT / "src" / "mcp_server.py",
        REPO_ROOT / "src" / "api" / "app.py",
        REPO_ROOT / "src" / "agents" / "graph.py",
        REPO_ROOT / "src" / "agents" / "review_store.py",
        REPO_ROOT / "src" / "retrieval" / "hybrid_search.py",
        REPO_ROOT / "src" / "retrieval" / "citation_graph.py",
        REPO_ROOT / "frontend" / "package.json",
        REPO_ROOT / "data" / "eval" / "real_queries_100.json",
        REPO_ROOT / "data" / "processed" / "chunks.jsonl",
    ]

    for p in critical_files:
        assert p.exists(), f"Critical SPEC artifact missing: {p}"
