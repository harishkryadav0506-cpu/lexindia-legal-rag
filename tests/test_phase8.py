"""
tests/test_phase8.py — Test suite for LexIndia Phase 8 Model Context Protocol (MCP) Server.

Strictly adheres to SPEC.md section #13 and section #15 (Phase 8):
- Tests FastMCP server tool discovery and registration:
  1. search_tax_law
  2. calculate_tax
  3. traverse_citation_graph
- Tests structured JSON citation outputs (section_id, source_url, page_number).
- Tests direct tool execution via FastMCP async interface.
- Tests full client-server connection over stdio using official mcp ClientSession.
- Verifies single source of truth across MCP tools and backend core engines.
"""

import os
import sys
import json
import pytest
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

from src.mcp_server import mcp
from src.agents.tools import calc_tax_old_vs_new


@pytest.mark.asyncio
async def test_mcp_tool_registration():
    """Verify all 3 mandated tools are registered on the FastMCP instance."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "search_tax_law" in tool_names
    assert "calculate_tax" in tool_names
    assert "traverse_citation_graph" in tool_names
    assert len(tool_names) == 3


@pytest.mark.asyncio
async def test_mcp_calculate_tax_direct():
    """Verify calculate_tax tool produces correct Old vs New slab breakdown and citations."""
    res = await mcp.call_tool(
        "calculate_tax",
        {"fy": "2025-26", "gross_income": 1500000.0, "deductions": {"80C": 150000.0, "80D": 25000.0}}
    )
    raw_text = res[0][0].text
    data = json.loads(raw_text)

    assert data["gross_income"] == 1500000.0
    assert data["fy"] == "2025-26"
    assert "old_regime" in data
    assert "new_regime" in data
    assert data["old_regime"]["total_tax"] > 0
    assert data["new_regime"]["total_tax"] > 0
    assert "comparison_table_md" in data
    assert "Section 115BAC" in data["comparison_table_md"]

    # Verify single source of truth: matches direct call
    direct_res = calc_tax_old_vs_new("2025-26", 1500000.0, {"80C": 150000.0, "80D": 25000.0})
    assert data["new_regime"]["total_tax"] == direct_res["new_regime"]["total_tax"]
    assert data["old_regime"]["total_tax"] == direct_res["old_regime"]["total_tax"]


@pytest.mark.asyncio
async def test_mcp_traverse_citation_graph_direct():
    """Verify traverse_citation_graph returns ego subgraph with nodes and typed edges."""
    res = await mcp.call_tool(
        "traverse_citation_graph",
        {"section_id": "Section 80C", "hops": 2}
    )
    raw_text = res[0][0].text
    data = json.loads(raw_text)

    assert data["section_id"] == "Section 80C"
    assert data["hops"] == 2
    assert data["node_count"] > 0
    assert data["edge_count"] > 0
    assert len(data["nodes"]) == data["node_count"]
    assert len(data["edges"]) == data["edge_count"]

    first_node = data["nodes"][0]
    assert "id" in first_node
    assert "authority_level" in first_node

    first_edge = data["edges"][0]
    assert "source" in first_edge
    assert "target" in first_edge
    assert "relation" in first_edge


@pytest.mark.asyncio
async def test_mcp_search_tax_law_direct():
    """Verify search_tax_law returns structured chunks with complete citations."""
    res = await mcp.call_tool(
        "search_tax_law",
        {"query": "turnover limit for tax audit under section 44AB", "financial_year": "2024-25"}
    )
    raw_text = res[0][0].text
    data = json.loads(raw_text)

    assert "query" in data
    assert data["count"] > 0
    assert len(data["chunks"]) == data["count"]

    for chunk in data["chunks"]:
        assert "chunk_id" in chunk and chunk["chunk_id"]
        assert "section_id" in chunk and chunk["section_id"]
        assert "doc_type" in chunk
        assert "authority_level" in chunk
        assert "source_url" in chunk and chunk["source_url"].startswith("http")
        assert "page_number" in chunk
        assert "score" in chunk
        assert "text" in chunk and len(chunk["text"]) > 0


@pytest.mark.asyncio
async def test_mcp_stdio_client_session_e2e():
    """
    End-to-end integration test:
    Launches MCP server process via stdio transport and communicates using ClientSession.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pytest.REPO_ROOT) if hasattr(pytest, "REPO_ROOT") else "."

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["src/mcp_server.py", "--transport", "stdio"],
        env=env
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # 1. Initialize
            init_res = await session.initialize()
            assert init_res is not None

            # 2. List tools
            tools_response = await session.list_tools()
            discovered = [t.name for t in tools_response.tools]
            assert "search_tax_law" in discovered
            assert "calculate_tax" in discovered
            assert "traverse_citation_graph" in discovered

            # 3. Call calculate_tax tool via client
            call_res = await session.call_tool(
                "calculate_tax",
                {"fy": "2024-25", "gross_income": 1000000.0, "deductions": {"80C": 150000.0}}
            )
            assert len(call_res.content) > 0
            payload = json.loads(call_res.content[0].text)
            assert payload["gross_income"] == 1000000.0
            assert "old_regime" in payload
            assert "new_regime" in payload

            # 4. Call traverse_citation_graph tool via client
            graph_res = await session.call_tool(
                "traverse_citation_graph",
                {"section_id": "Section 10(13A)", "hops": 1}
            )
            assert len(graph_res.content) > 0
            graph_payload = json.loads(graph_res.content[0].text)
            assert graph_payload["section_id"] == "Section 10(13A)"
            assert "nodes" in graph_payload
