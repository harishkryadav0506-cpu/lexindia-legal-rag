# LexIndia: Limitations, Evaluation Methodology & Known Boundaries

**Project**: Legal RAG System for Indian Tax Law Research
**Benchmark Reference**: 100 Real Government & Community Queries (`data/eval/real_queries_100.json`)
**Status Date**: 2026-09-20

---

## 1. Corpus Coverage Gaps

LexIndia's legal corpus is built exclusively from 30 official government documents covering the Income Tax Act 1961, Income Tax Rules 1962, Finance Acts (2020–2025), CBDT Circulars, and ITR Instructions. The following areas are **not yet covered** and will produce clean refusals:

- **TDS rate schedules** — Specific rate tables from Part II of the First Schedule are not separately ingested as structured data; queries about exact TDS rates for specific payment types may receive hedged or refused answers
- **Post-September 2025 amendments** — CBDT notifications and circulars published after the corpus build date are not indexed
- **GST, Companies Act, and other statutes** — Intentionally out of scope; the system refuses rather than guessing
- **State-level tax variations** — Professional tax, stamp duty, and state-specific provisions are not covered

The system's cite-or-refuse contract ensures these gaps result in honest refusals rather than hallucinated answers.

---

## 2. Chunk Section Labeling

Statutory PDF documents occasionally contain multiple sections on a single page. The chunking pipeline (`scripts/chunk_documents.py`) assigns `section_id` labels using regex patterns, which can produce:

- **Approximate assignments** — A chunk spanning Sections 10(10AA) through 10(10C) may be labeled with only one of those section IDs
- **Citation verifier drops** — The CitationVerifierAgent matches `[C#]` citation tags against chunk `section_id` fields; if the generator cites a section present in the chunk text but not in the `section_id` metadata, the citation is dropped as a "mismatch"

This is a known source of citation accuracy reduction and is targeted for improvement through finer-grained section boundary detection.

---

## 3. Evaluation Sample & Metric Provenance

### Headline Faithfulness: Stratified 50-Query Sample

The headline faithfulness score (**3.38 / 5.0**) is derived from a stratified **50-query sample** rather than the full 100-query benchmark:

- **16 Regenerated Queries**: All previously flagged edge cases that suffered from early cache contamination
- **15 Cross-Family Spot-Check Queries**: Balanced across 6 legal topics (DEDUCTION, CALCULATION, TDS_TCS, CAPITAL_GAINS, PROCEDURE, REFUSAL)
- **10 Corrected Statutory Refusal Queries**: Strict non-answer refusal verification
- **9 Standard Tax Research Queries**: Mainstream deduction and procedural queries

**Rationale**: Provider daily token-per-day (TPD) quota ceilings on Groq (`openai/gpt-oss-20b`, 200k daily ceiling) constrained live judging within a single 24-hour evaluation cycle.

### Configuration Split

| Evaluation Component | Configuration Layer |
|---|---|
| Retrieval Benchmark (Recall@K, MRR) | Post-Phase-3 tuned (statutory citation boosting + 5-fold cross-validated RRF, k=20) |
| End-to-End Generation (Citation, Refusal, Faithfulness) | Pre-Phase-3 baseline retrieval (default RRF k=40, top-8 chunks, 2-hop expansion) |

---

## 4. Judge Score Anchoring

The primary judge (`openai/gpt-oss-20b`) exhibits a pronounced midpoint anchoring heuristic:

- **Granular legal reasoning** is genuinely topic-specific — it identifies exact statutory provisions, numerical ceilings, and ungrounded clauses
- **Scoring discretization** — whenever an answer contains both verified citations and a minor extrapolation, the judge uniformly assigns **3/5** rather than graduating continuously between 2/5 and 4/5
- **Self-preference bias delta** — the diagnostic self-judge (`qwen/qwen3.8-27b`) scores +1.20 points higher than the cross-family judge, confirming the critical need for cross-model evaluation

### Rubric v2 (Active)

Rubric v2 explicitly decouples conversational helpfulness from legal faithfulness:
- Scores *only* whether factual and legal claims are supported by retrieved statutory context
- Faithful hedging ("the retrieved context does not provide the specific threshold") is scored as **fully faithful (5/5)**
- Deductions apply strictly to hallucinated section numbers, fabricated tax rates, or ungrounded claims

---

## 5. Test Database Isolation

The HITL integration tests (`tests/test_phase7.py`) create and manipulate review entries in temporary SQLite databases, but some test paths share state with the production `data/reviews.db`. Full test isolation with ephemeral per-test databases is deferred.

---

## 6. Hedge-Tag Placement

Low-confidence hedge markers (e.g., "*(note: retrieved context may not reflect the latest amendments)*") are injected per-chunk during answer generation. In edge cases involving markdown tables or multi-column layouts, hedge tags may appear inside table cells rather than as standalone notes below the table.

---

## 7. Model Ablation Status

- **Active production generator**: `qwen/qwen3.8-27b` (live via Groq), fully evaluated across the 100-query benchmark
- **Fallback generator**: `gemini-3.5-flash-lite` (Google GenAI), activated automatically on Groq 429 rate limits
- **Full `openai/gpt-oss-120b` ablation**: Deferred due to Groq TPM/TPD rate limits during project shipment; cataloged in `ABLATION_TABLE.md`

---

## 8. Deferred Roadmap Items

1. Full 100-query Rubric v2 faithfulness evaluation once provider 24-hour TPD limits reset
2. End-to-end pipeline evaluation on post-Phase-3 boosted retrieval (Recall@1 82.35%, MRR 0.8646)
3. Live `openai/gpt-oss-120b` vs `qwen/qwen3.8-27b` programmatic ablation
4. Elasticsearch HNSW vector indexing optimization for sub-10ms hybrid fusion latency
5. Per-citation claim-level semantic entailment verification
6. Ephemeral test database isolation for HITL integration tests
