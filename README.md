# LexIndia — Legal RAG System for Indian Tax Law Research

LexIndia is a production-grade, citation-grounded Retrieval-Augmented Generation (RAG) system engineered for Indian direct and indirect tax law research (Income Tax Act 1961, Income Tax Rules 1962, Finance Acts, CBDT circulars/notifications, and ITR instructions).

---

## 🏛️ System Architecture Overview

LexIndia combines:
1. **Real Government Corpus**: Zero synthetic data, authoritative sources with cryptographic verification.
2. **Hybrid Search + Cross-Encoder Reranking**: Elasticsearch 8.13 (BM25 + 768-dim BGE embeddings) fused with Reciprocal Rank Fusion (RRF) and BAAI/bge-reranker-base.
3. **Citation Knowledge Graph**: NetworkX directed citation graph (`READ_WITH`, `SUBJECT_TO`, `AMENDED_BY`, `EXPLAINS`) enabling multi-hop legal cross-reference retrieval.
4. **LangGraph Multi-Agent System with Human-in-the-Loop (HITL)**: Supervisor, Researcher, Calculator, and ComplianceVerifier agents with interruptible pause/resume on high stakes or low confidence.
5. **Model Context Protocol (FastMCP)**: Standardized tools over stdio/HTTP for Claude Desktop, Cursor, and IDEs.
6. **Dual LLM-as-Judge & Faithfulness Gates**: Entailment verification with fallback chains.

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10+
- Docker & Docker Compose
- Node.js 18+ (for frontend)

### Environment Setup
```bash
cp .env.example .env
# Edit .env with your GROQ_API_KEY and GEMINI_API_KEY
```

### Start Services (Elasticsearch, Backend, Frontend)
```bash
docker compose -f docker/docker-compose.yml up -d
```

---

## 🔌 Using LexIndia as an MCP Server

LexIndia implements the official Model Context Protocol (MCP) using the FastMCP Python SDK (`src/mcp_server.py`), exposing 3 citation-grounded tools over `stdio` and `streamable-http`:

1. **`search_tax_law`**: Hybrid BM25 + dense vector + cross-encoder retrieval returning top statutory chunks and citations with 2-hop statutory graph expansion.
2. **`calculate_tax`**: Deterministic slab computation comparing Old vs New Regime (Section 115BAC) with Standard Deduction (Section 16(ia)), Section 87A rebate, and 4% Health & Education Cess.
3. **`traverse_citation_graph`**: Multi-hop ego subgraph extraction showing typed legal relationships (`READ_WITH`, `SUBJECT_TO`, `AMENDED_BY`, `EXPLAINS`).

### Claude Desktop Configuration

To connect LexIndia to Claude Desktop or any MCP-compatible client (Cursor, Gemini CLI, Zed), add the following configuration snippet to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lexindia": {
      "command": "python",
      "args": [
        "d:\\LexIndia -----  Legal RAG System for Indian Tax Law\\src\\mcp_server.py",
        "--transport",
        "stdio"
      ],
      "env": {
        "PYTHONPATH": "d:\\LexIndia -----  Legal RAG System for Indian Tax Law",
        "GROQ_API_KEY": "your_groq_api_key_here",
        "GEMINI_API_KEY": "your_gemini_api_key_here",
        "ES_URL": "http://localhost:9200"
      }
    }
  }
}
```

### Running Standalone

Over `stdio`:
```bash
python src/mcp_server.py --transport stdio
```

Over `streamable-http`:
```bash
python src/mcp_server.py --transport streamable-http --host 127.0.0.1 --port 8001
```

---

*This document will be incrementally enriched as each phase progresses.*
