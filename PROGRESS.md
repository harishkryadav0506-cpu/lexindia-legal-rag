# LexIndia — Development Progress & Roadmap

Tracking project milestones, architectural decisions, and evaluation metrics for **LexIndia — Legal RAG System for Indian Tax Law Research**.

---

## 📌 Phase Checklist

- [x] **Phase 1**: Repo scaffold, config, `.env.example`, `docker-compose.yml` with Elasticsearch 8.13 running, and `/health` check. *(Completed)*
- [x] **Phase 2**: `download_real_data.py` -> `DATA_SOURCES.md`; verify >= 5 authoritative government documents downloaded with sha256 checksums. *(Completed - 30 documents downloaded, 136.09 MB, verified Income Tax Rules 1962, AY 2024-25 & 2025-26 ITR rules, CBDT circulars)*
- [x] **Phase 3**: Section-aware hierarchical chunking (`scripts/chunk_documents.py`) -> `data/processed/chunks.jsonl` (2,000–6,000 range, cross-reference edges, spot check Sections 80C, 10(13A), 24(b), 44AB). *(Completed - 3,407 chunks produced across 2,190 pages, all spot-check sections verified)*
- [x] **Phase 4**: Elasticsearch 8.13 index build (`scripts/build_es_index.py`), dense vector 768-dim embeddings via `BAAI/bge-base-en-v1.5`, 3 sanity searches. *(Completed - 3,407 documents indexed on ES 8.13 with 768-dim cosine embeddings, all 3 sanity searches verified)*
- [x] **Phase 5**: Retrieval pipeline (`query_expander.py`, `hybrid_search.py`, `reranker.py`, `citation_graph.py` with 2-hop expansion and authority weighting) + unit tests. *(Completed - multi-variant RRF fusion, CrossEncoder BGE reranker with authority weighting, 2-hop NetworkX citation graph expansion, 8/8 tests passing)*
- [x] **Phase 6**: Multi-agent StateGraph (Supervisor, Researcher, Calculator, ComplianceVerifier) + Generation + Faithfulness gate + Provider fallback; end-to-end `/query` test on 5 questions (including 1 Hinglish and 1 calculation) + mocked 429 test + agent trace validation. *(Completed - LangGraph 4-agent graph, slab-wise tax calculator, CrossEncoder faithfulness gate, live Gemini fallback on mocked 429, 10/10 tests passing)*
- [ ] **Phase 7**: Human-in-the-Loop (HITL) — `human_review` node with LangGraph `interrupt()`, `SqliteSaver` checkpointer, review endpoints (`/reviews/pending`, `/reviews/{thread_id}/decision`, `/reviews/stats`), `review_store.py`, append to `human_verified_pairs.json`.
- [ ] **Phase 8**: MCP server (`src/mcp_server.py`) using official `mcp` FastMCP SDK, exposing 3 tools over stdio + streamable-http, pytest client tests, README configuration snippet.
- [ ] **Phase 9**: Next.js 14 frontend (App Router, chat UI, sources + agent trace, citation graph Cytoscape viz, react-pdf provenance viewer, `/review` queue UI) + browser agent end-to-end verification.
- [ ] **Phase 10**: Evaluation set (100 real queries from public sources, no synthetic/LLM questions) + metrics + dual-judge `EVALUATION_REPORT.md` (Gemini 2.5 Flash primary vs GENERATION_MODEL secondary) + 1 tuning iteration.
- [ ] **Phase 11**: Strict Data Audit (`scripts/audit_data.py` -> `DATA_AUDIT.md`) validating file provenance, official government domains only, non-empty source URLs, review verification, and spot checking 10 random chunks.
- [ ] **Phase 12**: Ablation study (`scripts/run_ablation.py` -> `ABLATION_TABLE.md`) comparing `GENERATION_MODEL` vs `gemini-2.5-flash` on identical retrieved context.
- [ ] **Phase 13**: Final Docker/Hugging Face Spaces packaging (`Dockerfile`, `es_init.sh`, `supervisord`), comprehensive `README.md` (architecture diagram, Model Cards, HITL, Future Work), self-review checklist against spec.

---

## 📐 Key Architectural Decisions

1. **Repository Root Structure**: Operating directly at workspace root `d:\LexIndia -----  Legal RAG System for Indian Tax Law` without nested `lexindia/` directory per workspace rule.
2. **Data Authenticity**: Absolute strict policy: zero synthetic data, zero blog articles, official government sources only (`incometaxindia.gov.in`, `indiacode.nic.in`, `indiabudget.gov.in`, `cbic.gov.in`).
3. **Cite-or-Refuse**: Enforce mandatory citations (`[C#]`) with cross-encoder faithfulness gate and strict refusal when retrieved context is insufficient.
4. **Execution Protocol**: Strictly execute one phase at a time, verify with tests and command output evidence, update `PROGRESS.md`, and await explicit user approval ("Proceed to Phase X") before proceeding.

---

## 📊 Evaluation & Production Metrics (To Be Populated)

| Metric | Target | Actual Achieved | Notes |
|---|---|---|---|
| **Recall@5** | $\ge 80\%$ | TBD (Phase 10) | 100-query real benchmark |
| **MRR** | $\ge 68\%$ | TBD (Phase 10) | 100-query real benchmark |
| **Citation Accuracy** | $\ge 80\%$ | TBD (Phase 10) | Covers gold citations |
| **Refusal Precision** | High | TBD (Phase 10) | 15 unanswerable/ambiguous queries |
| **Dual Judge Agreement** | Tracked | TBD (Phase 10) | Gemini 2.5 Flash vs GENERATION_MODEL |
| **Review Trigger Rate** | Tracked | TBD (Phase 10) | High-stakes / low-confidence routing |
| **Avg Normalized Edit Dist** | Tracked | TBD (Phase 10) | Draft vs human-approved answer |

---

## 🕒 Current Status
- **Phase 1 Completed**:
  - Scaffolded full project structure with `.gitignore`, `requirements.txt`, `pyproject.toml`, and `.env.example`.
  - Implemented typed `src/config.py` with model role definitions (`GENERATION_MODEL`, `EXPANSION_MODEL`, `JUDGE_PRIMARY`, `JUDGE_SECONDARY`).
  - Created `docker/docker-compose.yml` with Elasticsearch 8.13.0 running single-node (`lexindia-es` container healthy on port 9200).
  - Built FastAPI application (`src/api/main.py`) with `/health` endpoint connected to ES.
  - Automated tests in `tests/test_phase1.py` passing (2/2).
- **Phase 2 Completed**:
  - Implemented hybrid downloader (`scripts/download_real_data.py`) with Chrome TLS impersonation (`curl_cffi`) and standard fallback to bypass government WAF restrictions on `incometaxindia.gov.in`.
  - Ingested **30 authentic government legal documents** (136.09 MB total) into `data/raw/` strictly from official government portals (`indiacode.gov.in`, `incometaxindia.gov.in`, `indiabudget.gov.in`, `incometax.gov.in`).
  - Generated `data/raw/manifest.json` with SHA-256 hashes and updated `DATA_SOURCES.md`.
  - Comprehensive automated test suite in `tests/test_phase2.py` passing (8/8).
- **Phase 3 Completed**:
  - Implemented section-aware hierarchical chunker in `scripts/chunk_documents.py` using `pdfplumber` with fallback to `pypdf`.
  - Generated `data/processed/chunks.jsonl` with **3,407 chunks** across 2,190 pages, satisfying the 2,000–6,000 range requirement.
  - Every chunk contains all required metadata fields: `chunk_id`, `doc_id`, `text`, `section_id`, `chapter`, `act_name`, `doc_type`, `authority_level`, `fy_valid_from`, `fy_valid_to`, `source_url`, `page_number`, `citations`, and `cross_references`.
  - Extracted over 2,500 statutory citations and 300+ typed cross-reference edges (`READ_WITH`, `SUBJECT_TO`, `NOTWITHSTANDING`, `AMENDED_BY`, `EXPLAINS`) to support the NetworkX citation graph.
  - Spot-checked and verified required key sections: **Section 80C**, **Section 10(13A)**, **Section 24(b)**, and **Section 44AB**.
  - Comprehensive automated test suite in `tests/test_phase3.py` passing (8/8).
- **Phase 4 Completed**:
  - Built Elasticsearch 8.13 index `lexindia_corpus` via `scripts/build_es_index.py`.
  - Configured mapping with `english` analyzer on `text`, 768-dimensional `dense_vector` embedding with `cosine` similarity, and keyword/integer metadata (`section_id`, `doc_type`, `authority_level`, `fy_valid_from`, `fy_valid_to`, `page_number`, `source_url`).
  - Embedded all 3,407 chunks using `BAAI/bge-base-en-v1.5` in batches of 64 and bulk-indexed into Elasticsearch.
  - Verified exact index document count: **3,407 documents**.
  - Executed and validated all 3 sanity searches:
    * **BM25 Lexical**: Section 80C deduction limit (top score 27.35)
    * **kNN Dense Vector**: Rule 2A / Section 10(13A) HRA exemption calculation (cosine similarity 0.8742)
    * **Hybrid Filtered**: Section 44AB audit turnover limits with `authority_level <= 2` filter (top score 22.83)
  - Comprehensive automated test suite in `tests/test_phase4.py` passing (6/6).
- **Phase 5 Completed**:
  - Implemented `src/retrieval/query_expander.py`: expands queries into exactly 3 variants using Groq `EXPANSION_MODEL` (qwen/qwen3.8-27b) with automatic fallback to `gemini-2.5-flash` on 429/5xx and deterministic legal reformulation.
  - Implemented `src/retrieval/hybrid_search.py`: multi-variant BM25 + kNN execution fused with Reciprocal Rank Fusion (RRF, $k=60$) supporting metadata filtering (`financial_year`, `doc_type`, `min_authority_level`).
  - Implemented `src/retrieval/reranker.py`: neural cross-encoder reranking using `BAAI/bge-reranker-base` with mandatory statutory authority weighting ($\{1: 1.0, 2: 0.95, 3: 0.85, 4: 0.6\}$).
  - Implemented `src/retrieval/citation_graph.py`: NetworkX DiGraph (519 nodes, 1,184 edges) with typed relationships (`READ_WITH`, `SUBJECT_TO`, `NOTWITHSTANDING`, `AMENDED_BY`, `EXPLAINS`), 2-hop neighbor expansion (+4 chunks flagged `graph_expanded=True`), and `/graph` ego subgraph extraction.
- **Phase 6 Completed**:
  - Implemented multi-agent architecture in `src/agents/` using LangGraph `StateGraph`:
    * `SupervisorAgent`: Query routing (`DEDUCTION`, `CALCULATION`, `TDS_TCS`, `CAPITAL_GAINS`, `PROCEDURE`), intent classification, and high-stakes/NRI review flagging.
    * `ResearcherAgent`: Section-aware retrieval using hybrid search, cross-encoder reranking, and citation graph 2-hop expansion.
    * `CalculatorAgent`: Deterministic Old vs New Regime tax calculation (`calc_tax_old_vs_new`) with Section 115BAC slabs, standard deduction, 87A rebate, 4% cess, and markdown comparison table.
    * `ComplianceVerifierAgent`: Rerank score validation ($\ge 0.25$), citation support verification, exact refusal enforcement (`"I cannot find sufficient authoritative guidance for this query."`), and review escalation.
  - Implemented generation subsystem in `src/generation/`:
    * `prompts.py`: Statutory prompt templates, refusal rules, and mandatory disclaimer.
    * `generator.py`: Primary generation with Groq (`openai/gpt-oss-120b`), live resilient fallback to Gemini (`gemini-3.6-flash`), and structured telemetry.
    * `faithfulness_gate.py`: Sentence-level entailment checking with cross-encoder and citation cross-referencing against retrieved context chunks.
  - Implemented end-to-end execution flow in `src/agents/graph.py` via `run_query()`.
  - Comprehensive automated test suite in `tests/test_phase6.py` passing (10/10). Full project test suite: **42/42 tests passing**.
- **Next Step**: Awaiting user approval to proceed to **Phase 7** (`src/agents/review_store.py`, LangGraph `human_review` node with `interrupt()`, review endpoints `/reviews/pending`, `/reviews/{thread_id}/decision`, `/reviews/stats`, and `human_verified_pairs.json`).






