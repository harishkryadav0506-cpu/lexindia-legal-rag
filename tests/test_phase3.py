"""
tests/test_phase3.py — Test suite for LexIndia Phase 3 Ingestion & Chunking.

Verifies SPEC.md section #4 and section #15 (Phase 3):
- Chunks file data/processed/chunks.jsonl exists and is non-empty.
- Chunk count is in the 2,000–6,000 range.
- Every chunk has all mandatory metadata fields per SPEC.
- Spot-checks sections 80C, 10(13A), 24(b), 44AB exist.
- Verifies citations and cross-reference edges are populated.
"""

import json
import os
from pathlib import Path
import pytest

CHUNKS_PATH = Path("data/processed/chunks.jsonl")


def test_chunks_file_exists_and_not_empty():
    assert CHUNKS_PATH.exists(), f"{CHUNKS_PATH} does not exist"
    assert CHUNKS_PATH.stat().st_size > 100_000, "chunks.jsonl is too small or empty"


def test_chunk_count_in_valid_range():
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    count = len(lines)
    assert 2000 <= count <= 6000, f"Expected chunk count in 2000-6000 range, got {count}"


def test_chunk_schema_and_fields():
    required_keys = {
        "chunk_id", "doc_id", "text", "section_id", "chapter",
        "doc_type", "authority_level", "fy_valid_from", "fy_valid_to",
        "source_url", "page_number"
    }
    valid_doc_types = {"statute", "rules", "finance_act", "circular", "itr_instructions"}
    valid_authority_levels = {1, 2, 3, 4}

    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            chunk = json.loads(line)
            # Check required keys
            missing = required_keys - set(chunk.keys())
            assert not missing, f"Chunk {idx} missing keys: {missing}"

            # Type and value assertions
            assert isinstance(chunk["chunk_id"], str) and chunk["chunk_id"].strip()
            assert isinstance(chunk["doc_id"], str) and chunk["doc_id"].strip()
            assert isinstance(chunk["text"], str) and len(chunk["text"].strip()) > 0
            assert isinstance(chunk["section_id"], str) and chunk["section_id"].strip()
            assert isinstance(chunk["chapter"], str)
            assert chunk["doc_type"] in valid_doc_types, f"Invalid doc_type: {chunk['doc_type']}"
            assert chunk["authority_level"] in valid_authority_levels
            assert isinstance(chunk["source_url"], str)
            assert isinstance(chunk["page_number"], int) and chunk["page_number"] >= 1
            assert isinstance(chunk.get("citations", []), list)
            assert isinstance(chunk.get("cross_references", []), list)


def test_spot_check_section_80c():
    found = False
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if "80C" in c["section_id"] or any("80C" in cit for cit in c.get("citations", [])):
                found = True
                break
    assert found, "Spot-check FAILED: Section 80C not found in any chunk section_id or citations"


def test_spot_check_section_10_13a():
    found = False
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if "10(13A)" in c["section_id"] or any("10(13A)" in cit for cit in c.get("citations", [])):
                found = True
                break
    assert found, "Spot-check FAILED: Section 10(13A) not found in any chunk section_id or citations"


def test_spot_check_section_24b():
    found = False
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if "24(b)" in c["section_id"] or any("24(b)" in cit for cit in c.get("citations", [])):
                found = True
                break
    assert found, "Spot-check FAILED: Section 24(b) not found in any chunk section_id or citations"


def test_spot_check_section_44ab():
    found = False
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if "44AB" in c["section_id"] or any("44AB" in cit for cit in c.get("citations", [])):
                found = True
                break
    assert found, "Spot-check FAILED: Section 44AB not found in any chunk section_id or citations"


def test_citations_and_cross_references_extracted():
    total_citations = 0
    total_cross_refs = 0
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            total_citations += len(c.get("citations", []))
            total_cross_refs += len(c.get("cross_references", []))
    assert total_citations > 500, f"Expected > 500 citations extracted, got {total_citations}"
    assert total_cross_refs > 100, f"Expected > 100 cross-references extracted, got {total_cross_refs}"
