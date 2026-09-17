"""
tests/test_phase11.py — Automated Unit Tests for Strict Data Audit (Phase 11).

Tests:
1. File integrity and cryptographic SHA-256 validation against manifest.
2. Domain whitelist verification (no commercial or third-party domains).
3. Benchmark query authenticity and forum URL provenance.
4. Anti-hallucination chunk verification against original raw PDFs.
5. Review store and human-verified training pairs integrity.
6. Full audit execution and report generation.
"""

import json
from pathlib import Path
import pytest

from src.config import settings
from scripts.audit_data import (
    compute_sha256,
    audit_raw_files_integrity,
    audit_domain_whitelist,
    audit_benchmark_provenance,
    audit_chunk_anti_hallucination_spotcheck,
    audit_review_store,
    run_full_data_audit,
    ALLOWED_GOV_DOMAINS,
    RAW_DIR,
    MANIFEST_PATH,
    PROCESSED_CHUNKS,
    BENCHMARK_PATH,
    AUDIT_REPORT_MD,
    AUDIT_RESULTS_JSON,
)


def test_raw_manifest_cryptographic_verification():
    """Verify that all manifest SUCCESS files exist and their SHA-256 matches."""
    assert MANIFEST_PATH.exists(), "manifest.json must exist in data/raw"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    res = audit_raw_files_integrity(manifest)
    assert res["passed"] is True, f"File integrity audit failed: {res.get('failed_files')}"
    assert len(res["verified_files"]) >= 20, "Must verify at least 20 official PDFs"
    assert len(res["failed_files"]) == 0, "Zero files should fail cryptographic verification"


def test_strict_domain_whitelist_enforcement():
    """Verify that 100% of URLs in manifest and chunks belong to official gov domains."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    res = audit_domain_whitelist(manifest)
    assert res["passed"] is True, f"Disallowed URLs encountered: {res.get('disallowed_urls')}"
    assert res["manifest_urls_checked"] >= 20
    assert res["chunk_urls_checked"] >= 2000
    assert len(res["disallowed_urls"]) == 0


def test_benchmark_queries_authenticity_and_urls():
    """Verify benchmark queries have valid forum URLs and proper gold citations."""
    res = audit_benchmark_provenance()
    assert res["passed"] is True, f"Benchmark provenance failed: {res}"
    assert res["total_queries"] == 100
    assert res["answerable_count"] == 85
    assert res["refusal_count"] == 15
    assert len(res["missing_url_queries"]) == 0
    assert len(res["invalid_gold_sections"]) == 0


def test_chunk_anti_hallucination_spotcheck():
    """Verify that 10 randomly sampled chunks match verbatim text in raw PDFs."""
    res = audit_chunk_anti_hallucination_spotcheck(sample_count=10, random_seed=42)
    assert res["passed"] is True, f"Spotcheck failed: {res}"
    assert len(res["spot_checks"]) == 10
    assert res["match_rate"] >= 80.0, f"Expected match rate >= 80%, got {res['match_rate']}%"
    for s in res["spot_checks"]:
        assert s["source_doc"] != "", "Chunk must specify valid source PDF"


def test_review_store_and_human_pairs_audit():
    """Verify SQLite review store and human-verified training pairs."""
    res = audit_review_store()
    assert res["passed"] is True, f"Review store audit failed: {res}"
    assert res["reviews_db_exists"] is True
    assert res["total_reviews"] > 0
    assert res["human_pairs_count"] > 0


def test_full_audit_workflow_and_artifact_generation():
    """Verify run_full_data_audit generates DATA_AUDIT.md and audit_results.json."""
    success = run_full_data_audit()
    assert success is True, "run_full_data_audit should return True"
    assert AUDIT_REPORT_MD.exists(), "DATA_AUDIT.md must exist"
    assert AUDIT_RESULTS_JSON.exists(), "audit_results.json must exist"

    md_content = AUDIT_REPORT_MD.read_text(encoding="utf-8")
    assert "ALL AUDIT CHECKS PASSED" in md_content
    assert "Check 1: Cryptographic Checksum" in md_content
    assert "Check 2: Official Government Domain Whitelist" in md_content
    assert "Check 3: Benchmark Dataset Provenance" in md_content
    assert "Check 4: Anti-Hallucination Chunk Spot-Checks" in md_content
    assert "Check 5: Human-in-the-Loop Review Store" in md_content
