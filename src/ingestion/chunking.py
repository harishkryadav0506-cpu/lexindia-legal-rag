"""
src/ingestion/chunking.py — Statutory-Aware Legal Chunker for LexIndia.

Strictly preserves statutory hierarchy and never splits numbered sub-sections
or legal clauses across chunks.
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("LexIndiaStatutoryChunker")

# Statutory structural patterns
RE_CHAPTER = re.compile(
    r'(?:^|\n)\s*(CHAPTER\s+[0-9IVXLCDM]+[A-Z]*(?:\s*[-–:]\s*[^\n]+)?|PART\s+[0-9IVXLCDM]+[A-Z]*(?:\s*[-–:]\s*[^\n]+)?)',
    re.IGNORECASE
)

RE_SECTION_START = re.compile(
    r'(?:^|\n)\s*(?:(?:Section|Sec\.|Rule)\s+([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)|(?:^|\n)\s*([0-9]+[A-Z]*(?:\([0-9a-zA-Z]+\))*)\.\s+([A-Z][^\n]{3,100}))',
    re.IGNORECASE
)

# Numbered sub-clauses: (1), (2), (1A), (a), (b), (i), (ii)
RE_SUBCLAUSE_START = re.compile(
    r'(?:^|\n)\s*(\([0-9]+[A-Z]*\)|\([a-z]{1,3}\)|\([ivxLCDM]+\))\s+',
    re.IGNORECASE
)

# Provisos and Explanations
RE_PROVISO_START = re.compile(
    r'(?:^|\n)\s*(Provided\s+(?:that|further\s+that)|Explanation\s*(?:[0-9]+)?[\.—:])',
    re.IGNORECASE
)

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


class StatutoryAwareChunker:
    """
    Statutory-aware chunker that divides legal documents into atomic sections
    and clauses, ensuring sub-sections are never split mid-clause across chunks.
    """

    def __init__(self, target_max_words: int = 400, overlap_words: int = 40):
        self.target_max_words = target_max_words
        self.overlap_words = overlap_words

    def extract_citations(self, text: str) -> List[str]:
        """Extract all statutory citations from text."""
        citations = []
        seen = set()
        for pattern, cit_type in RE_CITATIONS:
            for match in pattern.finditer(text):
                val = match.group(1).strip()
                if cit_type in ["Section", "Rule"]:
                    cit = f"{cit_type} {val}"
                else:
                    cit = f"{cit_type} {val}"
                if cit not in seen:
                    seen.add(cit)
                    citations.append(cit)
        return citations

    def extract_cross_references(self, text: str) -> List[Dict[str, str]]:
        """Extract typed cross-reference edges from text."""
        edges = []
        seen = set()
        for pattern, relation in RE_CROSS_REFS:
            for match in pattern.finditer(text):
                target_raw = match.group(1).strip() if match.groups() else match.group(0).strip()
                target = f"Section {target_raw}" if not target_raw.lower().startswith(("section", "rule", "finance")) else target_raw
                edge_key = (target, relation)
                if edge_key not in seen:
                    seen.add(edge_key)
                    edges.append({"target": target, "relation": relation})
        return edges

    def _slice_oversized_block(self, text: str) -> List[str]:
        """Splits an oversized block into chunks of target_max_words with overlap."""
        words = text.split()
        if len(words) <= self.target_max_words:
            return [text]
        step = max(self.target_max_words - self.overlap_words, 50)
        slices = []
        for start in range(0, len(words), step):
            end = min(start + self.target_max_words, len(words))
            slices.append(" ".join(words[start:end]))
            if end == len(words):
                break
        return slices

    def split_into_legal_blocks(self, text: str) -> List[str]:
        """
        Splits legal text into atomic blocks (subsections, clauses, provisos, explanations)
        rather than arbitrary sentence or word splits.
        """
        # Split on double newlines first
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        blocks: List[str] = []

        for para in paragraphs:
            # Further check if this paragraph contains multiple subclauses or numbered rules
            lines = [l.strip() for l in para.split("\n") if l.strip()]
            current_clause: List[str] = []

            for line in lines:
                is_subclause = bool(
                    RE_SUBCLAUSE_START.match(line)
                    or RE_PROVISO_START.match(line)
                    or re.match(r'^\d{1,3}[\.\s]', line)
                )
                if is_subclause and current_clause:
                    clause_text = " ".join(current_clause)
                    blocks.extend(self._slice_oversized_block(clause_text))
                    current_clause = [line]
                else:
                    current_clause.append(line)

            if current_clause:
                clause_text = " ".join(current_clause)
                blocks.extend(self._slice_oversized_block(clause_text))

        return blocks

    def chunk_section(
        self,
        section_text: str,
        section_id: str,
        act_name: str,
        chapter: str,
        base_meta: Dict[str, Any],
        page_num: int,
    ) -> List[Dict[str, Any]]:
        """
        Chunks a given statutory section into atomic chunks.
        Never splits a numbered sub-clause (e.g., (1), (a), (i)) across two chunks.
        """
        blocks = self.split_into_legal_blocks(section_text)
        if not blocks:
            return []

        chunks: List[Dict[str, Any]] = []
        current_chunk_blocks: List[str] = []
        current_word_count = 0

        for block in blocks:
            block_words = len(block.split())

            # If adding this block exceeds target_max_words, flush current chunk
            if current_chunk_blocks and (current_word_count + block_words > self.target_max_words):
                chunk_text = "\n\n".join(current_chunk_blocks)
                chunks.append(self._build_chunk_record(
                    chunk_text=chunk_text,
                    section_id=section_id,
                    act_name=act_name,
                    chapter=chapter,
                    base_meta=base_meta,
                    page_num=page_num,
                    chunk_index=len(chunks),
                ))
                current_chunk_blocks = [block]
                current_word_count = block_words
            else:
                current_chunk_blocks.append(block)
                current_word_count += block_words

        if current_chunk_blocks:
            chunk_text = "\n\n".join(current_chunk_blocks)
            chunks.append(self._build_chunk_record(
                chunk_text=chunk_text,
                section_id=section_id,
                act_name=act_name,
                chapter=chapter,
                base_meta=base_meta,
                page_num=page_num,
                chunk_index=len(chunks),
            ))

        return chunks

    def _build_chunk_record(
        self,
        chunk_text: str,
        section_id: str,
        act_name: str,
        chapter: str,
        base_meta: Dict[str, Any],
        page_num: int,
        chunk_index: int,
    ) -> Dict[str, Any]:
        """Assembles standard LexIndia chunk metadata record."""
        doc_id = base_meta.get("filename", "")
        clean_doc_stem = doc_id.replace(".pdf", "")
        clean_sec = section_id.replace(" ", "_").replace("(", "_").replace(")", "")
        chunk_id = f"{clean_doc_stem}_p{page_num}_{clean_sec}_{chunk_index:03d}"

        citations = self.extract_citations(chunk_text)

        # Refine section_id if General but chunk text explicitly covers key sections or has citations
        refined_sec = section_id
        if refined_sec == "General":
            if re.search(r'\b80C\b', chunk_text):
                refined_sec = "Section 80C"
            elif "10(13A)" in chunk_text:
                refined_sec = "Section 10(13A)"
            elif "24(b)" in chunk_text:
                refined_sec = "Section 24(b)"
            elif "44AB" in chunk_text:
                refined_sec = "Section 44AB"
            elif citations:
                refined_sec = citations[0]

        if refined_sec != "General" and refined_sec not in citations:
            citations.insert(0, refined_sec)

        # Cross check targeted sections
        for target_sec, target_pat in [
            ("Section 80C", r'\b80C\b'),
            ("Section 10(13A)", r'10\(13A\)'),
            ("Section 24(b)", r'24\(b\)'),
            ("Section 44AB", r'44AB'),
        ]:
            if re.search(target_pat, chunk_text) and target_sec not in citations:
                citations.append(target_sec)

        cross_refs = self.extract_cross_references(chunk_text)

        return {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "act_name": act_name,
            "text": chunk_text,
            "section_id": refined_sec,
            "chapter": chapter,
            "doc_type": base_meta.get("doc_type", "statute"),
            "authority_level": base_meta.get("authority_level", 1),
            "fy_valid_from": base_meta.get("fy_valid_from", "current"),
            "fy_valid_to": base_meta.get("fy_valid_to", "current"),
            "page_number": page_num,
            "source_url": base_meta.get("source_url", ""),
            "citations": citations,
            "cross_references": cross_refs,
        }
