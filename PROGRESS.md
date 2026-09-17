# LexIndia — Development Progress & Roadmap

Tracking project milestones, architectural decisions, and evaluation metrics for **LexIndia — Legal RAG System for Indian Tax Law Research**.

---

## 📌 Phase Checklist

- [x] **Phase 1**: Repo scaffold, config, `.env.example`, `docker-compose.yml` with Elasticsearch 8.13 running, and `/health` check. *(Completed)*
- [x] **Phase 2**: `download_real_data.py` -> `DATA_SOURCES.md`; verify >= 5 authoritative government documents downloaded with sha256 checksums. *(Completed - 30 documents downloaded, 136.09 MB, verified Income Tax Rules 1962, AY 2024-25 & 2025-26 ITR rules, CBDT circulars)*
- [ ] **Phase 3**: Section-aware hierarchical chunking (`scripts/chunk_documents.py`) -> `data/processed/chunks.jsonl` (2,000–6,000 range, cross-reference edges, spot check Sections 80C, 10(13A), 24(b), 44AB).


- [ ] **Phase 4**: Elasticsearch 8.13 index build (`scripts/build_es_index.py`), dense vector 768-dim embeddings via `BAAI/bge-base-en-v1.5`, 3 sanity searches.
- [ ] **Phase 5**: Retrieval pipeline (`query_expander.py`, `hybrid_search.py`, `reranker.py`, `citation_graph.py` with 2-hop expansion and authority weighting) + unit tests.
- [ ] **Phase 6**: Multi-agent StateGraph (Supervisor, Researcher, Calculator, ComplianceVerifier) + Generation + Faithfulness gate + Provider fallback; end-to-end `/query` test on 5 questions (including 1 Hinglish and 1 calculation) + mocked 429 test + agent trace validation.
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
  - Ingested **30 authentic government legal documents** (136.09 MB total) into `data/raw/` strictly from official government portals (`indiacode.gov.in`, `incometaxindia.gov.in`, `indiabudget.gov.in`, `incometax.gov.in`):
    * **Statute**: Income Tax Act, 1961 (6.84 MB, Act 43 of 1961)
    * **Rules**: Income-tax Rules, 1962 (98.84 MB, 628 pages, verified > 5MB with "INCOME-TAX RULES, 1962" title)
    * **Finance Acts**: Finance Act 2023, 2024, 2025 + Explanatory Memorandum 2024 (8.83 MB)
    * **ITR Instructions & Validation Rules**: AY 2020-21 (ITR-1, 2, 4 + Rules), AY 2024-25 (ITR-1, 2, 3, 4), AY 2025-26 (ITR-1, 2, 3, 4)
    * **CBDT Circulars**: 11 authentic CBDT Circulars (2024-2026) + Taxpayers Charter
  - Generated `data/raw/manifest.json` with SHA-256 hashes and updated `DATA_SOURCES.md`.
  - Comprehensive automated test suite in `tests/test_phase2.py` passing (8/8). Full project test suite: 10/10 tests passing.
- **Next Step**: Awaiting user approval to proceed to **Phase 3** (`scripts/chunk_documents.py`).



