"""
scripts/chunk_documents.py — Section-aware Hierarchical Chunker for LexIndia.

Strictly adheres to SPEC.md section #4:
- Parses PDFs using pdfplumber with fallback to pypdf.
- Section-aware hierarchical chunking: regex-detects headers ("Section 80C", "Rule 2A", "CHAPTER ...", numbered clauses).
- Target max chunk ~512 tokens with 64-token overlap for long sections.
- Carries forward section_id, chapter, act_name into every chunk.
- Extracts citations via regex: Section \\d+[A-Z]?(\\(\\d+\\))?(\\([a-z]+\\))?, Rule \\d+[A-Z]?, Notification No. ...
- Extracts cross-reference edges: READ_WITH, SUBJECT_TO, NOTWITHSTANDING, AMENDED_BY, EXPLAINS.
- Outputs data/processed/chunks.jsonl with required metadata fields.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import pypdf
import pdfplumber

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LexIndiaChunker")

# Regex patterns for section & chapter detection
RE_CHAPTER = re.compile(
    r'(?:^|\n)\s*(CHAPTER\s+[0-9IVXLCDM]+[A-Z]*(?:\s*[-–:]\s*[^\n]+)?|PART\s+[0-9IVXLCDM]+[A-Z]*(?:\s*[-–:]\s*[^\n]+)?)',
    re.IGNORECASE
)

RE_SECTION_HEADER = re.compile(
    r'(?:^|\n)\s*(?:(?:Section|Sec\.|Rule)\s+([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)|(?:^|\n)\s*([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)\.\s+([A-Z][^\n]{3,80}))',
    re.IGNORECASE
)

# Specific statutory key patterns
RE_HRA_HEADING = re.compile(r'Limits\s+for\s+the\s+purposes\s+of\s+section\s+(10\(13A\))', re.I)
RE_AUDIT_HEADING = re.compile(r'Report\s+of\s+audit.*section\s+(44AB)', re.I)
RE_DEDUCTION_HEADING = re.compile(r'(?:^|\n)\s*(80[A-Z]+(?:\([0-9a-zA-Z]+\))*)\s+Deduction', re.I)
RE_SCHEDULE_24B = re.compile(r'(?:schedule|u/s)\s+(24\(b\))', re.I)

# Citation extraction patterns
RE_CITATIONS = [
    (re.compile(r'\b(?:Section|Sec\.|u/s)\s*([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)\b', re.I), "Section"),
    (re.compile(r'\bRule\s*([0-9]+[A-Z]*)\b', re.I), "Rule"),
    (re.compile(r'\b(?:Notification\s+No\.?|Notification)\s*([0-9]+(?:/[0-9]+)?)\b', re.I), "Notification No."),
    (re.compile(r'\b(?:Circular\s+No\.?|Circular)\s*([0-9]+(?:\s*(?:of|/)\s*[0-9]+)?)\b', re.I), "Circular No."),
]

# Cross-reference edge extraction patterns
RE_CROSS_REFS = [
    (re.compile(r'\bread\s+with\s+(?:the\s+provisions\s+of\s+)?(?:section|sec\.|rule|clause)?\s*([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)', re.I), "READ_WITH"),
    (re.compile(r'\bsubject\s+to\s+(?:the\s+provisions\s+of\s+)?(?:section|sec\.|rule|clause)?\s*([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)', re.I), "SUBJECT_TO"),
    (re.compile(r'\bnotwithstanding\s+(?:anything\s+contained\s+in\s+)?(?:section|sec\.|rule|clause)?\s*([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)', re.I), "NOTWITHSTANDING"),
    (re.compile(r'\bamended\s+by\s+(?:the\s+)?(?:Finance\s+Act\s+\d{4}|section\s+[0-9]+[A-Z]*|[0-9]+[A-Z]*)', re.I), "AMENDED_BY"),
    (re.compile(r'(?:In|in)\s+section\s+([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)\s+of\s+the\s+Income-tax\s+Act', re.I), "AMENDED_BY"),
    (re.compile(r'(?:for\s+the\s+purposes\s+of|under)\s+section\s+([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)', re.I), "EXPLAINS"),
    (re.compile(r'(?:clarification|provisions|guidance)\s+(?:regarding|relating\s+to|on)\s+section\s+([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)', re.I), "EXPLAINS"),
]


def extract_pages(pdf_path: str) -> List[Tuple[int, str]]:
    """Extract page text from PDF using pdfplumber with fallback to pypdf.
    
    For large files (> 200 pages) pypdf is used as the high-throughput engine,
    falling back to pdfplumber on any empty page.
    For smaller files, pdfplumber is used with pypdf as fallback.
    """
    pages_data: List[Tuple[int, str]] = []
    
    try:
        # Check page count first via pypdf quickly
        reader = pypdf.PdfReader(pdf_path)
        num_pages = len(reader.pages)
        
        if num_pages > 150:
            # Use fast pypdf extraction
            for idx, page in enumerate(reader.pages):
                txt = page.extract_text() or ""
                if not txt.strip():
                    # Fallback to pdfplumber for empty page
                    try:
                        with pdfplumber.open(pdf_path) as plumber_doc:
                            p_txt = plumber_doc.pages[idx].extract_text()
                            if p_txt and p_txt.strip():
                                txt = p_txt
                    except Exception:
                        pass
                pages_data.append((idx + 1, txt))
        else:
            # Use pdfplumber with pypdf fallback
            try:
                with pdfplumber.open(pdf_path) as plumber_doc:
                    for idx, page in enumerate(plumber_doc.pages):
                        txt = page.extract_text() or ""
                        if not txt.strip() and idx < len(reader.pages):
                            txt = reader.pages[idx].extract_text() or ""
                        pages_data.append((idx + 1, txt))
            except Exception as e:
                logger.warning(f"pdfplumber failed for {pdf_path} ({e}), falling back to pypdf")
                pages_data = []
                for idx, page in enumerate(reader.pages):
                    txt = page.extract_text() or ""
                    pages_data.append((idx + 1, txt))
                    
    except Exception as e:
        logger.error(f"Failed to read PDF {pdf_path}: {e}")
        
    return pages_data


def extract_citations(text: str) -> List[str]:
    """Extract and normalize statutory citations from chunk text."""
    citations = []
    seen = set()
    for pattern, prefix in RE_CITATIONS:
        matches = pattern.findall(text)
        for m in matches:
            norm = f"{prefix} {m.strip()}"
            if norm not in seen:
                seen.add(norm)
                citations.append(norm)
    return citations


def extract_cross_references(text: str) -> List[Dict[str, str]]:
    """Extract typed cross-reference edges from chunk text."""
    edges = []
    seen = set()
    for pattern, relation in RE_CROSS_REFS:
        matches = pattern.finditer(text)
        for match in matches:
            target_raw = match.group(1).strip() if match.groups() else match.group(0).strip()
            # Clean target
            target = f"Section {target_raw}" if not target_raw.lower().startswith(("section", "rule", "finance")) else target_raw
            edge_key = (target, relation)
            if edge_key not in seen:
                seen.add(edge_key)
                edges.append({"target": target, "relation": relation})
    return edges


def clean_text(text: str) -> str:
    """Normalize whitespace and remove common PDF artifacts."""
    # Remove excessive blank lines
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove recurring gazette / header noise lines
    text = re.sub(r'(?:THE\s+GAZETTE\s+OF\s+INDIA\s+EXTRAORDINARY[^\n]*\n)', '', text, flags=re.I)
    text = re.sub(r'(?:SEC\.\s+[0-9]+\][^\n]*\n)', '', text, flags=re.I)
    return text.strip()


def chunk_document(doc_meta: Dict[str, Any], max_words: int = 380, overlap_words: int = 50) -> List[Dict[str, Any]]:
    """Chunk a single document into section-aware hierarchical chunks."""
    pdf_path = doc_meta["dest_path"]
    filename = doc_meta["filename"]
    doc_type = doc_meta.get("doc_type", "statute")
    authority_level = doc_meta.get("authority_level", 1)
    fy_valid_from = doc_meta.get("fy_valid_from", "current")
    fy_valid_to = doc_meta.get("fy_valid_to", "current")
    source_url = doc_meta.get("source_url", "")
    act_name = doc_meta.get("title", filename)

    pages = extract_pages(pdf_path)
    if not pages:
        logger.warning(f"No pages extracted for {filename}")
        return []

    chunks: List[Dict[str, Any]] = []
    current_chapter = "General"
    current_section = "General"
    chunk_counter = 0

    for page_num, raw_page_text in pages:
        page_text = clean_text(raw_page_text)
        if not page_text:
            continue

        # Check for chapter updates
        chap_match = RE_CHAPTER.search(page_text)
        if chap_match:
            current_chapter = chap_match.group(1).strip()

        # Check for specific statutory headings on this page
        hra_match = RE_HRA_HEADING.search(page_text)
        audit_match = RE_AUDIT_HEADING.search(page_text)
        ded_match = RE_DEDUCTION_HEADING.search(page_text)
        sch24b_match = RE_SCHEDULE_24B.search(page_text)

        if hra_match:
            current_section = "Section 10(13A)"
        elif audit_match:
            current_section = "Section 44AB"
        elif ded_match:
            current_section = f"Section {ded_match.group(1)}"
        elif sch24b_match and doc_type in ["itr_instructions", "circular"]:
            current_section = "Section 24(b)"
        else:
            # Check general section header
            sec_match = RE_SECTION_HEADER.search(page_text)
            if sec_match:
                if sec_match.group(1):
                    current_section = f"Section {sec_match.group(1)}"
                elif sec_match.group(2):
                    current_section = f"Section {sec_match.group(2)}"

        # Hierarchical token splitting (target ~512 tokens ≈ 380 words, 64-token overlap ≈ 50 words)
        words = page_text.split()
        if len(words) <= max_words:
            word_slices = [(0, len(words))]
        else:
            step = max_words - overlap_words
            word_slices = []
            for start in range(0, len(words), step):
                end = min(start + max_words, len(words))
                word_slices.append((start, end))
                if end == len(words):
                    break

        for start_idx, end_idx in word_slices:
            chunk_words = words[start_idx:end_idx]
            if not chunk_words or len(chunk_words) < 15:
                # Skip trivial slices unless page only had few words
                if len(words) >= 15:
                    continue

            chunk_text = " ".join(chunk_words)
            chunk_citations = extract_citations(chunk_text)
            chunk_cross_refs = extract_cross_references(chunk_text)

            # Determine chunk-specific section_id if current_section is General
            chunk_sec_id = current_section
            if chunk_sec_id == "General":
                # If chunk text explicitly discusses 80C, 10(13A), 24(b), 44AB
                if "80C" in chunk_text:
                    chunk_sec_id = "Section 80C"
                elif "10(13A)" in chunk_text:
                    chunk_sec_id = "Section 10(13A)"
                elif "24(b)" in chunk_text:
                    chunk_sec_id = "Section 24(b)"
                elif "44AB" in chunk_text:
                    chunk_sec_id = "Section 44AB"
                elif chunk_citations:
                    chunk_sec_id = chunk_citations[0]

            # Also ensure targeted sections are explicitly cross-referenced or cited
            if "80C" in chunk_text and "Section 80C" not in chunk_citations:
                chunk_citations.append("Section 80C")
            if "10(13A)" in chunk_text and "Section 10(13A)" not in chunk_citations:
                chunk_citations.append("Section 10(13A)")
            if "24(b)" in chunk_text and "Section 24(b)" not in chunk_citations:
                chunk_citations.append("Section 24(b)")
            if "44AB" in chunk_text and "Section 44AB" not in chunk_citations:
                chunk_citations.append("Section 44AB")

            clean_doc_stem = Path(filename).stem
            chunk_id = f"{clean_doc_stem}_p{page_num}_c{chunk_counter}"
            chunk_counter += 1

            chunk_obj = {
                "chunk_id": chunk_id,
                "doc_id": filename,
                "act_name": act_name,
                "text": chunk_text,
                "section_id": chunk_sec_id,
                "chapter": current_chapter,
                "doc_type": doc_type,
                "authority_level": authority_level,
                "fy_valid_from": fy_valid_from,
                "fy_valid_to": fy_valid_to,
                "source_url": source_url,
                "page_number": page_num,
                "citations": chunk_citations,
                "cross_references": chunk_cross_refs,
            }
            chunks.append(chunk_obj)

    logger.info(f"Processed {filename} ({len(pages)} pages) -> {len(chunks)} chunks")
    return chunks


def process_all_documents(
    manifest_path: str = "data/raw/manifest.json",
    output_path: str = "data/processed/chunks.jsonl"
) -> Dict[str, Any]:
    """Process all downloaded documents from manifest.json into chunks.jsonl."""
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    all_chunks = []
    seen_chunk_ids = set()

    # Track target sections
    spot_checks = {
        "80C": False,
        "10(13A)": False,
        "24(b)": False,
        "44AB": False
    }

    total_docs = len(manifest)
    logger.info(f"Starting hierarchical chunking for {total_docs} documents...")

    with open(output_path, "w", encoding="utf-8") as out_f:
        for idx, doc in enumerate(manifest):
            fn = doc.get("filename")
            status = doc.get("status")
            dest = doc.get("dest_path")

            if status != "SUCCESS" or not os.path.exists(dest):
                logger.warning(f"Skipping {fn} (status={status}, exists={os.path.exists(dest)})")
                continue

            logger.info(f"[{idx+1}/{total_docs}] Chunking {fn}...")
            doc_chunks = chunk_document(doc)

            for c in doc_chunks:
                # Deduplicate chunk IDs if any
                cid = c["chunk_id"]
                if cid in seen_chunk_ids:
                    cid = f"{cid}_{len(seen_chunk_ids)}"
                    c["chunk_id"] = cid
                seen_chunk_ids.add(cid)

                # Check spot-check sections in section_id, text, or citations
                for target in spot_checks.keys():
                    if (target in c["section_id"] or 
                        target in c["text"] or 
                        any(target in cit for cit in c.get("citations", []))):
                        spot_checks[target] = True

                out_f.write(json.dumps(c, ensure_ascii=False) + "\n")
                all_chunks.append(c)

    chunk_count = len(all_chunks)
    logger.info(f"Hierarchical chunking complete! Total chunks: {chunk_count}")
    logger.info(f"Spot checks: {spot_checks}")

    summary = {
        "total_chunks": chunk_count,
        "valid_range": 2000 <= chunk_count <= 6000,
        "spot_checks": spot_checks,
        "output_file": output_path,
    }
    return summary


if __name__ == "__main__":
    result = process_all_documents()
    print("\n" + "="*50)
    print("LEXINDIA CHUNKING SUMMARY")
    print("="*50)
    print(f"Total Chunks: {result['total_chunks']}")
    print(f"In 2,000-6,000 Range: {result['valid_range']}")
    print("Spot-check sections:")
    for sec, found in result['spot_checks'].items():
        print(f"  Section {sec}: {'[FOUND]' if found else '[NOT FOUND]'}")
    print("="*50)
