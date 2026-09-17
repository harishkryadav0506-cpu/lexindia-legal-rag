"""
Tests for Phase 2: Real Data Download Verification and Cryptographic Integrity.
"""

import json
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from src.config import settings

ALLOWED_GOV_DOMAINS = {
    "incometaxindia.gov.in",
    "incometax.gov.in",
    "indiabudget.gov.in",
    "cbic.gov.in",
    "gstcouncil.gov.in",
    "indiacode.nic.in",
    "indiacode.gov.in",
    "itat.gov.in",
    "sci.gov.in",
}


def test_manifest_and_files_count():
    """Verify manifest exists and >= 5 documents downloaded per SPEC Phase 2."""
    manifest_path = settings.RAW_DATA_DIR / "manifest.json"
    assert manifest_path.exists(), "data/raw/manifest.json must exist"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest) >= 5, f"Expected >= 5 downloaded documents, found {len(manifest)}"


def test_cryptographic_checksums_and_file_existence():
    """Verify every file in manifest exists on disk and its SHA-256 matches."""
    manifest_path = settings.RAW_DATA_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for item in manifest:
        file_path = Path(item["dest_path"])
        assert file_path.exists(), f"File {file_path} missing from disk"
        assert file_path.stat().st_size > 1000, f"File {file_path} is unexpectedly small or empty"

        # Verify SHA-256
        content = file_path.read_bytes()
        actual_sha = hashlib.sha256(content).hexdigest()
        assert actual_sha == item["sha256"], f"SHA256 mismatch for {item['filename']}"


def test_strict_domain_whitelist_provenance():
    """Verify every source URL belongs strictly to authorized government domains."""
    manifest_path = settings.RAW_DATA_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for item in manifest:
        url = item["source_url"]
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        assert domain in ALLOWED_GOV_DOMAINS or any(
            domain.endswith("." + d) for d in ALLOWED_GOV_DOMAINS
        ), f"Disallowed domain '{domain}' for source URL: {url}"


def test_data_sources_markdown_integrity():
    """Verify DATA_SOURCES.md contains documented records and checksums."""
    data_sources_md = settings.DATA_DIR.parent / "DATA_SOURCES.md"
    assert data_sources_md.exists(), "DATA_SOURCES.md must exist"

    content = data_sources_md.read_text(encoding="utf-8")
    assert "Income Tax Act, 1961" in content
    assert "Finance Act 2024" in content
    assert "SHA-256 Checksum" in content
