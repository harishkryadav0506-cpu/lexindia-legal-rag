"""
src/agents/tools.py — Retrieval, Citation Graph, and Tax Calculation Tools.

Strictly adheres to SPEC.md section #7:
- retrieve_sections: Executes hybrid search + cross-encoder reranking (top-8).
- traverse_citation_graph: 2-hop traversal via {READ_WITH, SUBJECT_TO, AMENDED_BY} (+4 chunks).
- calc_tax_old_vs_new: Computes slab-wise tax comparing Old Regime vs New Regime (Section 115BAC),
  including Standard Deduction, Section 87A rebate, and 4% Health & Education Cess,
  returning computation table with statutory citations.
"""

import logging
from typing import List, Dict, Any, Optional

from src.retrieval.hybrid_search import HybridSearcher
from src.retrieval.reranker import Reranker
from src.retrieval.citation_graph import CitationGraph

logger = logging.getLogger("LexIndiaAgentTools")

# Cached tool engine singletons
_searcher: Optional[HybridSearcher] = None
_reranker: Optional[Reranker] = None
_graph: Optional[CitationGraph] = None


def get_searcher() -> HybridSearcher:
    global _searcher
    if _searcher is None:
        _searcher = HybridSearcher()
    return _searcher


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def get_graph() -> CitationGraph:
    global _graph
    if _graph is None:
        _graph = CitationGraph()
    return _graph


def retrieve_sections(
    query: str,
    financial_year: Optional[str] = None,
    doc_type: Optional[str] = None,
    min_authority_level: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Retrieve top-8 candidate chunks using hybrid search + cross-encoder reranking."""
    searcher = get_searcher()
    reranker = get_reranker()

    candidates = searcher.search(
        query=query,
        financial_year=financial_year,
        doc_type=doc_type,
        min_authority_level=min_authority_level,
        top_k=30
    )
    top_8 = reranker.rerank(query=query, candidates=candidates, top_n=8)
    return top_8


def traverse_citation_graph(top_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Expand top chunks with up to 4 neighbor chunks via NetworkX 2-hop traversal."""
    graph = get_graph()
    expanded = graph.expand_chunks(top_chunks, max_expansion=4)
    return expanded


def calc_tax_old_vs_new(
    fy: str,
    gross_income: float,
    deductions: Optional[Dict[str, float]] = None,
    is_salaried: bool = True
) -> Dict[str, Any]:
    """
    Slab-wise tax computation comparing Old Regime vs New Regime (Section 115BAC).
    
    Supports FY 2024-25 and FY 2025-26 slab structures:
    - Standard deduction:
        * Old Regime: Rs 50,000 (Salaried)
        * New Regime: Rs 75,000 (FY 2025-26) / Rs 50,000 (FY 2024-25)
    - Section 87A rebate:
        * Old Regime: up to Rs 12,500 if taxable income <= 5,00,000
        * New Regime: up to Rs 25,000 if taxable income <= 7,00,000
    - 4% Health & Education Cess
    """
    deductions = deductions or {}

    # Standard deduction
    old_std_ded = 50000.0 if is_salaried else 0.0
    new_std_ded = 75000.0 if (is_salaried and "2025-26" in fy) else (50000.0 if is_salaried else 0.0)

    # Old Regime Deductions
    sec_80c = min(deductions.get("80C", 0.0), 150000.0)
    sec_80d = min(deductions.get("80D", 0.0), 50000.0)
    sec_24b = min(deductions.get("24(b)", 0.0), 200000.0)
    other_ded = deductions.get("other", 0.0)
    total_old_deductions = old_std_ded + sec_80c + sec_80d + sec_24b + other_ded

    old_taxable_income = max(0.0, gross_income - total_old_deductions)

    # Calculate Old Regime Tax
    # Slabs: 0-2.5L: 0%, 2.5-5L: 5%, 5-10L: 20%, >10L: 30%
    old_tax = 0.0
    if old_taxable_income > 1000000:
        old_tax += (old_taxable_income - 1000000) * 0.30
        old_tax += 500000 * 0.20
        old_tax += 250000 * 0.05
    elif old_taxable_income > 500000:
        old_tax += (old_taxable_income - 500000) * 0.20
        old_tax += 250000 * 0.05
    elif old_taxable_income > 250000:
        old_tax += (old_taxable_income - 250000) * 0.05

    # Section 87A rebate for Old Regime
    if old_taxable_income <= 500000:
        old_rebate = min(old_tax, 12500.0)
    else:
        old_rebate = 0.0
    old_tax_after_rebate = max(0.0, old_tax - old_rebate)
    old_cess = old_tax_after_rebate * 0.04
    total_old_tax = round(old_tax_after_rebate + old_cess)

    # New Regime (Section 115BAC)
    new_taxable_income = max(0.0, gross_income - new_std_ded)

    # New Slabs (FY 2025-26 per Finance Act 2025):
    # 0-3L: 0%, 3-7L: 5%, 7-10L: 10%, 10-12L: 15%, 12-15L: 20%, >15L: 30%
    new_tax = 0.0
    if new_taxable_income > 1500000:
        new_tax += (new_taxable_income - 1500000) * 0.30
        new_tax += 300000 * 0.20
        new_tax += 200000 * 0.15
        new_tax += 300000 * 0.10
        new_tax += 400000 * 0.05
    elif new_taxable_income > 1200000:
        new_tax += (new_taxable_income - 1200000) * 0.20
        new_tax += 200000 * 0.15
        new_tax += 300000 * 0.10
        new_tax += 400000 * 0.05
    elif new_taxable_income > 1000000:
        new_tax += (new_taxable_income - 1000000) * 0.15
        new_tax += 300000 * 0.10
        new_tax += 400000 * 0.05
    elif new_taxable_income > 700000:
        new_tax += (new_taxable_income - 700000) * 0.10
        new_tax += 400000 * 0.05
    elif new_taxable_income > 300000:
        new_tax += (new_taxable_income - 300000) * 0.05

    # Section 87A rebate for New Regime
    if new_taxable_income <= 700000:
        new_rebate = min(new_tax, 25000.0)
    else:
        new_rebate = 0.0
    new_tax_after_rebate = max(0.0, new_tax - new_rebate)
    new_cess = new_tax_after_rebate * 0.04
    total_new_tax = round(new_tax_after_rebate + new_cess)

    tax_difference = total_old_tax - total_new_tax
    recommended = "New Tax Regime (Section 115BAC)" if tax_difference >= 0 else "Old Tax Regime"

    # Format markdown comparison table
    table_md = (
        f"### Tax Computation Comparison ({fy})\n\n"
        f"| Component | Old Tax Regime | New Tax Regime (Sec 115BAC) |\n"
        f"| :--- | :--- | :--- |\n"
        f"| **Gross Total Income** | Rs {gross_income:,.0f} | Rs {gross_income:,.0f} |\n"
        f"| **Standard Deduction** | Rs {old_std_ded:,.0f} [C1] | Rs {new_std_ded:,.0f} [C2] |\n"
        f"| **Chapter VI-A Deductions (80C, 80D, 24b)** | Rs {sec_80c+sec_80d+sec_24b:,.0f} [C3] | *Not Available* |\n"
        f"| **Total Deductions** | Rs {total_old_deductions:,.0f} | Rs {new_std_ded:,.0f} |\n"
        f"| **Taxable Income** | Rs {old_taxable_income:,.0f} | Rs {new_taxable_income:,.0f} |\n"
        f"| **Calculated Base Tax** | Rs {old_tax:,.0f} | Rs {new_tax:,.0f} |\n"
        f"| **Rebate u/s 87A** | -Rs {old_rebate:,.0f} | -Rs {new_rebate:,.0f} [C4] |\n"
        f"| **Health & Education Cess (4%)** | Rs {old_cess:,.0f} | Rs {new_cess:,.0f} |\n"
        f"| **Total Tax Payable** | **Rs {total_old_tax:,.0f}** | **Rs {total_new_tax:,.0f}** |\n\n"
        f"**Recommendation:** **{recommended}** saves **Rs {abs(tax_difference):,.0f}** annually."
    )

    return {
        "gross_income": gross_income,
        "financial_year": fy,
        "old_regime": {
            "deductions": total_old_deductions,
            "taxable_income": old_taxable_income,
            "base_tax": old_tax,
            "rebate_87a": old_rebate,
            "cess": old_cess,
            "total_tax": total_old_tax
        },
        "new_regime": {
            "deductions": new_std_ded,
            "taxable_income": new_taxable_income,
            "base_tax": new_tax,
            "rebate_87a": new_rebate,
            "cess": new_cess,
            "total_tax": total_new_tax
        },
        "tax_difference": tax_difference,
        "recommended_regime": recommended,
        "comparison_table_md": table_md
    }
