"""
Tests for Phase 2: Authoritative Tax Law Corpus Ingestion Verification.
Validates presence of Act 1961, Rules 1962, Finance Acts, ITR instructions (AY 2024-25, AY 2025-26),
CBDT circulars, cryptographic checksums, and strict government domain whitelist.
"""

import json
import hashlib
from pathlib import Path
from urllib.parse import urlparse
import pypdf
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
    """Verify manifest exists and contains >= 20 authoritative documents."""
    manifest_path = settings.RAW_DATA_DIR / "manifest.json"
    assert manifest_path.exists(), "data/raw/manifest.json must exist"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest) >= 20, f"Expected >= 20 downloaded documents, found {len(manifest)}"


def test_income_tax_rules_1962_integrity():
    """Verify Income Tax Rules 1962 is > 5 MB and has required title text on page 1."""
    rules_path = settings.RAW_DATA_DIR / "income_tax_rules_1962.pdf"
    assert rules_path.exists(), "income_tax_rules_1962.pdf must exist in data/raw"
    size_mb = rules_path.stat().st_size / (1024 * 1024)
    assert size_mb > 5.0, f"Income Tax Rules 1962 must be > 5 MB, got {size_mb:.2f} MB"

    reader = pypdf.PdfReader(str(rules_path))
    assert len(reader.pages) >= 100, f"Expected comprehensive rules (> 100 pages), got {len(reader.pages)}"
    text_p1 = reader.pages[0].extract_text().upper()
    assert "INCOME-TAX" in text_p1 or "RULES" in text_p1, "Page 1 must contain 'INCOME-TAX' or 'RULES'"


def test_core_statutes_and_finance_acts_present():
    """Verify Income Tax Act 1961 and Finance Acts 2023, 2024, 2025 are present."""
    required_files = [
        "income_tax_act_1961.pdf",
        "finance_act_2023.pdf",
        "finance_act_2024.pdf",
        "finance_act_2025.pdf",
    ]
    for fn in required_files:
        p = settings.RAW_DATA_DIR / fn
        assert p.exists(), f"Required core document {fn} missing"
        assert p.stat().st_size > 100_000, f"Core document {fn} unexpectedly small"


def test_current_ay_itr_instructions_present():
    """Verify current AY 2024-25 and AY 2025-26 ITR documents are present."""
    required_itr = [
        "itr1_validation_rules_ay2024_25.pdf",
        "itr2_validation_rules_ay2024_25.pdf",
        "itr3_validation_rules_ay2024_25.pdf",
        "itr4_validation_rules_ay2024_25.pdf",
        "itr1_validation_rules_ay2025_26.pdf",
        "itr2_validation_rules_ay2025_26.pdf",
        "itr3_validation_rules_ay2025_26.pdf",
        "itr4_validation_rules_ay2025_26.pdf",
    ]
    for fn in required_itr:
        p = settings.RAW_DATA_DIR / fn
        assert p.exists(), f"Current AY ITR document {fn} missing"
        assert p.stat().st_size > 10_000, f"ITR document {fn} unexpectedly small"


def test_cbdt_circulars_present():
    """Verify CBDT circulars are downloaded and valid PDFs."""
    manifest_path = settings.RAW_DATA_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    circulars = [m for m in manifest if m["doc_type"] == "circular"]
    assert len(circulars) >= 10, f"Expected >= 10 CBDT circulars, found {len(circulars)}"


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
    assert "Income-tax Rules, 1962" in content
    assert "Finance Act 2024" in content
    assert "CBDT Circular" in content
    assert "SHA-256 Checksum" in content
