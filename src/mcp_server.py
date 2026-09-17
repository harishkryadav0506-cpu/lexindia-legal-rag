"""
src/mcp_server.py — Model Context Protocol (MCP) Server for LexIndia.

Strictly adheres to SPEC.md section #13 and section #15 (Phase 8):
- Implements official FastMCP server from mcp Python SDK exposing exactly 3 tools:
  1. search_tax_law(query: str, financial_year: str | None) -> top-8 cited chunks (+ graph expansion)
  2. calculate_tax(fy: str, gross_income: float, deductions: dict | None) -> slab-wise breakdown with citations
  3. traverse_citation_graph(section_id: str, hops: int) -> typed subgraph summary
- Reuses the EXACT same retrieval, graph, and calculation pipelines from src/agents/tools.py (single source of truth).
- Exposes tools over stdio and streamable-http transports.
"""

import json
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

# Ensure repo root is in sys.path when invoked directly or via stdio
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp.server.fastmcp import FastMCP

from src.config import settings
from src.agents.tools import retrieve_sections, traverse_citation_graph as expand_via_graph, calc_tax_old_vs_new
from src.retrieval.citation_graph import CitationGraph

logger = logging.getLogger("LexIndiaMCPServer")

# Initialize FastMCP Server
mcp = FastMCP(
    name="LexIndia Tax Law MCP Server",
    instructions=(
        "Official Model Context Protocol (MCP) Server for Indian Income Tax Law Research. "
        "Provides grounding tools for statutory searches, Old vs New Regime slab calculations, "
        "and statutory cross-reference graph traversal directly from authentic government legal texts."
    )
)

_cached_graph: Optional[CitationGraph] = None


def _get_graph() -> CitationGraph:
    global _cached_graph
    if _cached_graph is None:
        _cached_graph = CitationGraph()
    return _cached_graph


@mcp.tool()
def search_tax_law(query: str, financial_year: Optional[str] = "2024-25") -> str:
    """
    Search Indian tax law corpus using hybrid retrieval (BM25 + BGE dense vector + cross-encoder reranker).
    Returns top cited chunks with exact section IDs, authority levels, source URLs, page numbers, and text.
    
    Args:
        query: Tax law question or statutory topic (e.g. 'Section 80C deduction limit' or 'HRA exemption calculation')
        financial_year: Target Assessment/Financial Year context (e.g. '2024-25' or '2025-26')
    """
    try:
        # Retrieve top-8 candidates via hybrid search + cross-encoder
        top_8 = retrieve_sections(query=query, financial_year=financial_year)
        # Expand with up to 4 neighbor chunks via NetworkX 2-hop statutory graph
        expanded_chunks = expand_via_graph(top_8)

        formatted_chunks = []
        for c in expanded_chunks:
            formatted_chunks.append({
                "chunk_id": c.get("chunk_id"),
                "section_id": c.get("section_id"),
                "doc_type": c.get("doc_type"),
                "authority_level": c.get("authority_level"),
                "source_url": c.get("source_url"),
                "page_number": c.get("page_number"),
                "score": round(float(c.get("score", 0.0)), 4),
                "graph_expanded": bool(c.get("graph_expanded", False)),
                "text": c.get("text", "").strip()
            })

        result = {
            "query": query,
            "financial_year": financial_year,
            "count": len(formatted_chunks),
            "chunks": formatted_chunks
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error executing search_tax_law: {e}", exc_info=True)
        return json.dumps({"error": str(e), "query": query, "chunks": []})


@mcp.tool()
def calculate_tax(
    fy: str,
    gross_income: float,
    deductions: Optional[Dict[str, float]] = None
) -> str:
    """
    Calculate deterministic slab-wise income tax comparing Old Regime vs New Regime (Section 115BAC).
    Includes Standard Deduction (Section 16(ia)), Section 87A rebate, and 4% Health & Education Cess.
    
    Args:
        fy: Financial year (e.g. '2024-25' or '2025-26')
        gross_income: Annual gross total income in INR (e.g. 1500000)
        deductions: Optional dictionary of Old Regime deductions (e.g. {'80C': 150000, '80D': 25000})
    """
    try:
        res = calc_tax_old_vs_new(
            fy=fy,
            gross_income=float(gross_income),
            deductions=deductions or {},
            is_salaried=True
        )
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error executing calculate_tax: {e}", exc_info=True)
        return json.dumps({"error": str(e), "fy": fy, "gross_income": gross_income})


@mcp.tool()
def traverse_citation_graph(section_id: str, hops: int = 2) -> str:
    """
    Traverse the statutory cross-reference network around a target section.
    Extracts an ego subgraph showing typed legal relations (READ_WITH, SUBJECT_TO, AMENDED_BY, EXPLAINS).
    
    Args:
        section_id: Target statutory provision (e.g. 'Section 80C', 'Section 10(13A)', or 'Section 115BAC')
        hops: Traversal depth in the knowledge graph (1 to 3 hops, default 2)
    """
    try:
        cg = _get_graph()
        subgraph = cg.get_subgraph(section_id=section_id, hops=hops)
        result = {
            "section_id": section_id,
            "hops": hops,
            "node_count": len(subgraph.get("nodes", [])),
            "edge_count": len(subgraph.get("edges", [])),
            "nodes": subgraph.get("nodes", []),
            "edges": subgraph.get("edges", [])
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error executing traverse_citation_graph: {e}", exc_info=True)
        return json.dumps({"error": str(e), "section_id": section_id, "nodes": [], "edges": []})


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LexIndia Model Context Protocol (MCP) Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport mode (stdio | streamable-http | sse)"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Binding host for HTTP server")
    parser.add_argument("--port", type=int, default=8001, help="Binding port for HTTP server")
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    elif args.transport == "sse":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
