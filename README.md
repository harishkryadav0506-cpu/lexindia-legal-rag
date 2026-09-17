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

*This document will be incrementally enriched as each phase progresses.*
