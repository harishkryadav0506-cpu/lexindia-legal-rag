WORKSPACE RULE: The currently open folder IS the repo root. Do NOT create a nested 'lexindia/' subfolder — create ALL structure (data/, scripts/, src/, frontend/, docker/, tests/, and root docs) directly in the current directory.
Before starting Phase 1, save this entire specification verbatim as SPEC.md in the repo root.
After each phase, show evidence (file lists / command outputs) and WAIT for my explicit "Proceed to Phase X" command.



IMPORTANT EXECUTION RULE: Read this entire specification. First, initialize the repo, create the folder structure, setup PROGRESS.md, and STOP. Do NOT write all the code for all phases at once. Execute strictly ONE PHASE AT A TIME. After completing a phase, show me the summary/tests and WAIT for my command "Proceed to Phase X" before starting the next.

You are a senior AI/ML engineer and legal-tech architect. Build a production-grade project named "LexIndia — Legal RAG System for Indian Tax Law Research" from scratch in this workspace. Follow this specification EXACTLY. Do not skip sections. Work phase by phase, verify each phase, and maintain a PROGRESS.md file updated after every phase (completed phases, decisions taken, actual metrics).

# 0. GLOBAL RULES
- Use ONLY real, authoritative government data sources. NO synthetic corpora. NO blog articles as primary sources.
- Every answer must be citation-grounded (cite-or-refuse). If evidence is insufficient, the system MUST refuse.
- Human-in-the-loop: low-confidence or high-stakes answers MUST route to an expert review queue; human-approved corrections are treated as real, verified data.
- Modular, typed Python (type hints), pytest tests for core utils, docstrings everywhere.
- All secrets via .env (provide .env.example with GROQ_API_KEY, HF_TOKEN, GEMINI_API_KEY, LLM_PROVIDER, GENERATION_MODEL, EXPANSION_MODEL, optional LANGFUSE keys, ENABLE_GST, ES_URL). Never hardcode keys.
- Structured logging for every pipeline stage; optional Langfuse/Phoenix tracing behind env flag.
- Target metrics are GOALS: Recall@5 >= 80%, MRR >= 68%, Citation Accuracy >= 80% on the 100-query benchmark. Report ACTUAL achieved numbers in EVALUATION_REPORT.md (honesty over inflation).
- Gemini must NEVER be used for ingestion, chunking, or eval-question creation. The real-data-only rule applies to all models.
- After each phase: run tests, print a short summary of what was built + how to verify it, then WAIT for approval.

# 1. TECH STACK (MANDATORY — do not substitute)
- Backend: Python 3.11+, FastAPI
- Frontend: Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui + Radix, lucide-react, react-markdown + remark-gfm, TanStack Query, react-pdf (pdf.js), cytoscape.js, sonner, next-themes, zod. Do NOT use Redux, MUI, or Ant Design.
- Search: Elasticsearch 8.13 (BM25 + dense_vector 768-dim, cosine similarity)
- Embeddings: BAAI/bge-base-en-v1.5 (768-dim, run locally)
- Reranker: BAAI/bge-reranker-base cross-encoder (run locally)
- Query-expansion LLM (role EXPANSION_MODEL): qwen/qwen3.8-27b (via Groq)
- Generation LLM (role GENERATION_MODEL): openai/gpt-oss-120b (via Groq)
- Judge + fallback LLM: gemini-2.5-flash (google-genai SDK, GEMINI_API_KEY)
- Provider config: LLM_PROVIDER env (groq default | together | hf), OpenAI-compatible client per provider (base_url + key from env)
- Multi-agent orchestration + HITL: LangGraph (typed StateGraph, SqliteSaver checkpointer, interrupt/resume)
- Citation graph: NetworkX (typed DiGraph)
- MCP server: official `mcp` Python SDK (FastMCP), stdio + streamable-http
- Runtime faithfulness gate: cross-encoder entailment (bge-reranker-base as NLI proxy)
- Review store: SQLite (data/reviews.db, gitignored)
- Deployment: Docker + docker-compose; Hugging Face Spaces Docker Space config
- Evaluation: custom metrics scripts + dual LLM-as-judge (Gemini primary, GENERATION_MODEL secondary)

# 2. REPO STRUCTURE (create exactly)
lexindia/
├── README.md
├── EVALUATION_REPORT.md
├── DATA_SOURCES.md
├── DATA_AUDIT.md
├── ABLATION_TABLE.md
├── PROGRESS.md
├── .env.example
├── requirements.txt
├── pyproject.toml
├── data/
│   ├── raw/                  (gitignored)
│   ├── processed/            (gitignored)
│   ├── reviews.db            (gitignored)
│   └── eval/
│       ├── real_queries_100.json
│       └── human_verified_pairs.json
├── scripts/
│   ├── download_real_data.py
│   ├── chunk_documents.py
│   ├── build_es_index.py
│   ├── build_citation_graph.py
│   ├── build_eval_set.py
│   ├── audit_data.py
│   └── run_ablation.py
├── src/
│   ├── config.py
│   ├── ingestion/
│   ├── retrieval/
│   │   ├── query_expander.py
│   │   ├── hybrid_search.py
│   │   ├── reranker.py
│   │   └── citation_graph.py
│   ├── agents/
│   │   ├── graph.py            (multi-agent StateGraph + human_review interrupt)
│   │   ├── agents.py           (Supervisor/Researcher/Calculator/ComplianceVerifier prompts)
│   │   ├── tools.py
│   │   └── review_store.py     (SQLite reviews table)
│   ├── generation/
│   │   ├── prompts.py
│   │   ├── generator.py
│   │   └── faithfulness_gate.py
│   ├── evaluation/
│   │   ├── metrics.py
│   │   └── llm_judge.py
│   ├── mcp_server.py
│   └── api/
│       ├── main.py
│       └── schemas.py
├── frontend/                 (Next.js app incl. /review queue page)
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── es_init.sh
└── tests/

# 3. REAL DATA SOURCES (scripts/download_real_data.py)
Primary (must-have):
1. Income Tax Act, 1961 — official PDF, incometaxindia.gov.in (Acts section). Fallback: indiacode.nic.in
2. Income Tax Rules, 1962 — official PDF, incometaxindia.gov.in
3. Finance Acts 2023, 2024, 2025 — PDFs from indiabudget.gov.in
4. Top ~50 CBDT circulars/notifications (2020-2026) — incometaxindia.gov.in circulars page
5. ITR-1 to ITR-4 instructions (AY 2024-25 and AY 2025-26) — incometax.gov.in downloads
Secondary (behind ENABLE_GST=true flag, later phase):
6. CGST Act 2017, IGST Act 2017 — cbic.gov.in
Rules:
- Metadata per document: source_url, doc_type (statute|rules|finance_act|circular|itr_instructions), authority_level (1=Act, 2=Rules, 3=Circular/Notification, 4=Instructions), financial-year validity where applicable, downloaded_at.
- If a URL fails: log it, continue, and record it in DATA_SOURCES.md with status FAILED + reason. Never fabricate content.
- DATA_SOURCES.md must list every file actually downloaded with URL + sha256 checksum.
- Respect robots.txt, 1s delay between requests, descriptive browser User-Agent header, retry with exponential backoff.

# 4. INGESTION & CHUNKING (scripts/chunk_documents.py)
- Parse PDFs with pdfplumber (fallback pypdf).
- Section-aware hierarchical chunking: regex-detect headers ("Section 80C", "Rule 2A", "CHAPTER ...", numbered clauses); max chunk ~512 tokens with 64-token overlap for long sections; carry forward section_id, chapter, act_name into every chunk.
- Extract citations via regex: Section \d+[A-Z]?(\(\d+\))?(\([a-z]+\))?, Rule \d+[A-Z]?, Notification No. ...
- Extract cross-reference edges from phrases: "read with", "subject to", "notwithstanding", and Finance Act amendment links ("amended by") for the NetworkX graph.
- Output data/processed/chunks.jsonl with fields: chunk_id, doc_id, text, section_id, chapter, doc_type, authority_level, fy_valid_from, fy_valid_to, source_url, page_number.

# 5. ELASTICSEARCH INDEX (scripts/build_es_index.py)
- Index: lexindia_corpus on ES 8.13 (docker-compose service, single-node, security disabled for dev).
- Mapping: text (english analyzer), embedding (dense_vector dims=768, cosine), keyword/int metadata: section_id, doc_type, authority_level, fy_valid_from, fy_valid_to, page_number, source_url.
- Embed all chunks with bge-base-en-v1.5 locally (batch 64). Verify doc count and run 3 sanity queries; print results.

# 6. RETRIEVAL PIPELINE (src/retrieval/)
- query_expander.py: EXPANSION_MODEL (default qwen/qwen3.8-27b, temp 0.3) produces exactly 3 variants: (a) formal legal phrasing with probable section references, (b) layman English, (c) English legal reformulation if input is Hinglish/colloquial, else a keyword-boosted variant.
- hybrid_search.py: per variant run ES hybrid query (BM25 on text + kNN on embedding, top 20 each); fuse ALL variant lists with Reciprocal Rank Fusion (k=60); support metadata filters: financial_year, doc_type, min_authority_level.
- reranker.py: bge-reranker-base over fused top 30 -> return top 8 with scores.
- citation_graph.py: NetworkX DiGraph from chunks.jsonl cross-references + Finance Act amendment edges; typed edges: READ_WITH, SUBJECT_TO, AMENDED_BY, EXPLAINS. 2-hop expansion: for top-8 chunks pull neighbors via {READ_WITH, SUBJECT_TO, AMENDED_BY}, append up to +4 neighbor chunks flagged graph_expanded=true.
- Authority weighting: final_score = rerank_score * weight; weights = {1: 1.0, 2: 0.95, 3: 0.85, 4: 0.6}.

# 7. MULTI-AGENT LAYER + HUMAN-IN-THE-LOOP (src/agents/)
- LangGraph typed StateGraph (LexIndiaState) with 4 distinct agents, each with its own system prompt:
  * SupervisorAgent — routing + coordination; classifies query: DEDUCTION | TDS_TCS | CAPITAL_GAINS | PROCEDURE | CALCULATION | GST | UNKNOWN; sets review_required flag
  * ResearcherAgent — retrieval + citation-graph traversal (uses retrieve_sections, traverse_citation_graph tools)
  * CalculatorAgent — slab-wise tax computation (uses calc_tax_old_vs_new tool; answer must include computation table + citations)
  * ComplianceVerifierAgent — faithfulness gate + authority check; sets must_refuse if best rerank score < threshold (default 0.25) or entailment < 0.5
- agent_trace: every agent appends {agent, action, latency_ms, inputs_summary, outputs_summary} to state; returned in /query response and shown in UI.
- HUMAN-IN-THE-LOOP (mandatory):
  * human_review node placed after ComplianceVerifierAgent, before final response.
  * review_required=True when: confidence < 0.6, OR route in HIGH_STAKES = {CAPITAL_GAINS, TDS_TCS, NRI-related}, OR must_refuse=True (escalation), OR request flag require_review=true.
  * Implement with LangGraph interrupt() inside human_review node + SqliteSaver checkpointer; graph pauses exposing draft_answer + citations + thread_id; resumes on Command(resume=decision).
  * Decisions: approve | edit (with edited_answer) | reject (with reviewer_note -> final response becomes refusal + note).
  * review_store.py: SQLite table reviews(id, thread_id, query, financial_year, draft_answer, citations_json, action, final_answer, reviewer_note, created_at).
  * Human-approved (action=edit or approve with high edit quality) query+final pairs are appended to data/eval/human_verified_pairs.json as REAL verified data for future benchmark extension. Never auto-generate these pairs.

# 8. GENERATION + SAFETY + FALLBACK (src/generation/)
- prompts.py: system prompt = Indian tax legal research assistant; MUST cite every claim as [C#] mapped to chunk metadata; MUST refuse with exact phrase "I cannot find sufficient authoritative guidance for this query." when context is insufficient; include selected FY context; append one-line disclaimer.
- generator.py: GENERATION_MODEL (default openai/gpt-oss-120b) via Groq, temperature 0.1, max_tokens 1024; input = question + top-8 chunks (+ graph-expanded) with chunk IDs; output = markdown answer with inline [C1]..[C8] citations.
- PROVIDER FALLBACK (mandatory): in generator.py AND query_expander.py, if Groq returns 429/5xx after retries, automatically route the same request to gemini-2.5-flash and log a structured fallback event (model_from, model_to, reason, latency).
- faithfulness_gate.py: runtime entailment check between answer sentence-clusters and their cited chunks via cross-encoder; if mean entailment < 0.5 or a citation has no supporting chunk -> mark low_confidence or convert to refusal.

# 9. FASTAPI BACKEND (src/api/)
- POST /query {question, financial_year?, taxpayer_type?, require_review?} -> if review triggered: {status: "awaiting_review", thread_id, draft_answer, citations, agent_trace}; else {status: "complete", answer, citations: [{chunk_id, section_id, doc_type, source_url, page_number, score, graph_expanded}], confidence, refused, route, latency_ms, fallback_used, agent_trace}
- POST /reviews/{thread_id}/decision {action: approve|edit|reject, edited_answer?, reviewer_note?} -> resumes graph, returns final response object
- GET /reviews/pending -> queue list (thread_id, query, draft, citations, age_minutes)
- GET /reviews/stats -> {approval_rate, edit_rate, reject_rate, avg_normalized_edit_distance, review_trigger_rate}
- GET /graph?section_id=X&hops=2 -> nodes/edges JSON for frontend visualization
- GET /health
- CORS for frontend origin; rate limit 30 req/min.

# 10. NEXT.JS FRONTEND (frontend/)
- Chat UI: query box + FY selector (2022-23 ... 2026-27) + taxpayer-type dropdown (salaried/self-employed/NRI/senior-citizen); zod-validated input; "Request expert review" toggle (sets require_review).
- Answer card: markdown rendering via react-markdown; citation chips [C1]..; clicking a chip opens a side Sheet showing chunk text with matched spans highlighted + "View original source" button that opens the react-pdf viewer at source_url#page=N with highlight overlay.
- Status badges: confidence badge, "Awaiting expert review" badge with thread_id, refusal banner, low_confidence warning, fallback_used indicator (which model generated).
- Sources tab: retrieved chunks table (rerank score, authority weight, graph_expanded) + agent_trace timeline visualization.
- Review Queue page (/review): pending drafts list; review panel with markdown editor for edits, approve/edit/reject buttons, reviewer note field; after decision the final answer appears in the original chat thread (poll or SSE refresh).
- "Citation Graph" tab: force-directed graph of /graph subgraph for the last query; node color by authority_level; edge labels by relation type; clicking a node shows that section's text.
- Optional /metrics page: recharts dashboard visualizing key numbers from EVALUATION_REPORT.md plus live /reviews/stats.
- Optional streaming: if backend exposes SSE endpoint /query/stream, stream tokens into the answer card; keep non-streaming /query as default for evaluation reproducibility.
- Responsive layout with dark mode; lazy-load (dynamic import) the pdf viewer and graph components.
- Footer disclaimer: "LexIndia provides legal information, not professional tax advice."

# 11. EVALUATION (scripts/build_eval_set.py + src/evaluation/)
- Build 100 REAL queries ONLY: collect real user questions from public sources (Reddit r/IndianIncomeTax threads, official incometax.gov.in FAQs, public community Q&A). NO synthetic questions. NO LLM-generated questions. Manually map each to gold citations (section IDs present in downloaded corpus). Include 15 real unanswerable/ambiguous queries for refusal testing.
- Store data/eval/real_queries_100.json: {id, question, source_forum_url, gold_citations[], gold_fy?, topic}.
- metrics.py: Recall@5, MRR, Citation Accuracy (answers whose citations cover gold_citations), Refusal Precision, latency p50/p95.
- Human-loop metrics from /reviews/stats: approval_rate, edit_rate, reject_rate, avg_normalized_edit_distance (draft vs approved), review_trigger_rate. Report in EVALUATION_REPORT.md.
- llm_judge.py DUAL JUDGE: PRIMARY judge = gemini-2.5-flash (cross-model judging of GENERATION_MODEL answers to avoid self-preference bias); SECONDARY judge = GENERATION_MODEL. Score faithfulness 1-5 per answer vs retrieved chunks. Report BOTH scores side-by-side in EVALUATION_REPORT.md with inter-judge agreement rate.
- EVALUATION_REPORT.md: actual numbers, per-topic tables, top-10 failure analysis with reasons, human-loop metrics section.
- GitHub Action: on PRs touching src/ or data/, run a 20-query smoke eval.

# 12. ABLATION STUDY (scripts/run_ablation.py)
- Run the 100-query benchmark twice over IDENTICAL retrieved context: (a) generation = GENERATION_MODEL (openai/gpt-oss-120b), (b) generation = gemini-2.5-flash.
- Compare generation-only metrics: Citation Accuracy, faithfulness (both judges), Refusal Precision, latency p50/p95.
- RULE: retrieval stack (ES/BGE/RRF/rerank/graph) MUST NOT change between runs — only the generation model swaps. Cache retrieved context once and reuse for both runs.
- Output ABLATION_TABLE.md with side-by-side table + 3-paragraph analysis of which model grounds citations better and why.

# 13. MCP SERVER (src/mcp_server.py)
- Use official `mcp` Python SDK (FastMCP); expose exactly 3 tools over stdio + streamable-http:
  1. search_tax_law(query: str, financial_year: str | None) -> top-8 cited chunks (same retrieval pipeline as /query, generation excluded)
  2. calculate_tax(fy: str, gross_income: float, deductions: dict) -> slab-wise breakdown with citations
  3. traverse_citation_graph(section_id: str, hops: int) -> typed subgraph summary
- Each tool returns structured JSON including citations (section_id, source_url, page_number) so any MCP client (Claude Desktop, Gemini CLI, Cursor) can ground its own answers in LexIndia retrieval.
- pytest tests: spin up the MCP server, list tools, call each tool once via an MCP client.
- README: "Using LexIndia as an MCP server" section with a claude_desktop_config.json snippet.
- RULE: MCP tools reuse the exact same retrieval/calculation code paths as the FastAPI backend (single source of truth), no duplicated logic.

# 14. DEPLOYMENT
- docker-compose services: elasticsearch:8.13.0, backend (FastAPI), frontend (Next.js); mount a volume for data/reviews.db so review history survives restarts.
- docker/Dockerfile for HF Spaces Docker Space: cold-start script es_init.sh starts ES, builds/loads index from bundled data/processed, then supervisord starts backend + frontend in one container.
- README.md: setup steps, env vars, mermaid architecture diagram (include agents + human_review interrupt + MCP server), evaluation summary table, ablation summary, HITL workflow explanation, demo instructions, disclaimer, Future Work section, Model Cards table (exact model IDs + provider used at evaluation time).

# 15. EXECUTION ORDER (strict; verify each phase, then WAIT for approval)
Phase 1: repo scaffold + config + .env.example + docker-compose with ES running + /health check.
Phase 2: download_real_data.py -> DATA_SOURCES.md; verify >= 5 documents downloaded with checksums.
Phase 3: chunking -> chunks.jsonl; verify chunk count in 2,000-6,000 range; spot-check sections 80C, 10(13A), 24(b), 44AB exist.
Phase 4: ES index build + 3 sanity searches printed.
Phase 5: retrieval pipeline (expander, hybrid, RRF, reranker, citation graph) + unit tests.
Phase 6: multi-agent graph (4 agents) + generation + faithfulness gate + provider fallback; end-to-end /query test on 5 questions (include 1 Hinglish query and 1 calculation query); test fallback path with a mocked Groq 429; verify agent_trace populated.
Phase 7: HITL — human_review interrupt + SqliteSaver checkpointing + review endpoints + review_store; tests: interrupt -> resume with approve, with edit, with reject; verify human_verified_pairs.json append on edit.
Phase 8: MCP server + pytest client tests + README MCP snippet.
Phase 9: frontend (chat, sources + agent_trace, graph viz, PDF provenance viewer, /review queue UI) connected to backend; use browser agent to verify a full query flow AND one review flow end-to-end.
Phase 10: eval set (100 real queries) + metrics + dual-judge EVALUATION_REPORT.md incl. human-loop metrics; ONE tuning iteration allowed (RRF k / top-k / threshold) to improve MRR; record before/after.
Phase 11: STRICT DATA AUDIT — create scripts/audit_data.py and run it to produce DATA_AUDIT.md:
  - Check 1: List every file in data/raw and data/processed with its source URL and sha256 from DATA_SOURCES.md.
  - Check 2: Verify every source URL belongs ONLY to: incometaxindia.gov.in, incometax.gov.in, indiabudget.gov.in, cbic.gov.in, gstcouncil.gov.in, indiacode.nic.in, itat.gov.in, sci.gov.in. Flag anything else.
  - Check 3: Parse data/eval/real_queries_100.json and verify EVERY question has a non-empty source_forum_url pointing to a real public thread or official FAQ page; also verify every entry in human_verified_pairs.json has a reviewer decision record in reviews.db.
  - Check 4: Spot-check 10 random chunks from data/processed against their source document pages to ensure no LLM-generated/hallucinated legal text was injected during ingestion.
  - RULE: DO NOT fix anything by generating data. Only produce DATA_AUDIT.md with PASS/FAIL per item and a flagged-entries table. If any FAIL, halt execution and alert me.
Phase 12: run_ablation.py -> ABLATION_TABLE.md (identical cached context for both generation models).
Phase 13: final Docker/HF Spaces packaging + README (incl. Future Work section) + self-review checklist against this spec.

# 16. DEFINITION OF DONE
- POST /query returns cited answers for: "Can I claim both HRA and home loan interest deduction?", "kya main apne rent ka deduction le sakta hu?", "TDS rate on rent above Rs 50,000 per month?", "old vs new regime for 15 lakh income FY 2025-26".
- HITL flow verified: require_review=true query -> status awaiting_review with thread_id -> POST decision with edit -> final answer reflects the edit and pair lands in human_verified_pairs.json.
- MCP verified: list_tools + one call per tool via test client succeeds.
- EVALUATION_REPORT.md (dual-judge scores + agreement rate + human-loop metrics), DATA_SOURCES.md, DATA_AUDIT.md (ALL PASS), and ABLATION_TABLE.md exist with real content.
- Provider fallback verified via mocked 429 test.
- docker compose up brings the full stack; README is reproducible by a stranger.
- Zero synthetic data anywhere; every source traceable in DATA_SOURCES.md and verified in DATA_AUDIT.md.

# 17. FUTURE WORK (document in README only — do NOT build now)
- LoRA/PEFT fine-tuning of bge-reranker-base once >= 200 REAL supervision pairs accumulate (human_verified_pairs.json + real_queries gold mappings); include reasoning for why retrieval-first was chosen initially.
- Multimodal parsing of PDF tables/charts via a vision model.
- Hindi/multilingual retrieval via BGE-M3 embeddings.
- State-level tax extensions (professional tax, stamp duty).

# 18. MODEL ROLES & PROVIDER CONFIG (final, frozen)
- config.py defines model ROLES via env, never hardcodes provider strings:
  * GENERATION_MODEL: default "openai/gpt-oss-120b" (Groq)
  * EXPANSION_MODEL: default "qwen/qwen3.8-27b" (Groq)
  * JUDGE_PRIMARY: "gemini-2.5-flash"; JUDGE_SECONDARY: value of GENERATION_MODEL
- LLM_PROVIDER env: groq (primary) | together | hf (OpenAI-compatible client per provider, base_url + key from env).
- Fallback chain on 429/5xx after retries: Groq GENERATION_MODEL -> gemini-2.5-flash.
- Everywhere this spec names a concrete model for generation or expansion, the configured role value wins at runtime.
