# LexIndia: Architectural Boundaries, Evaluation Methodology & Known Limitations

**Project**: Legal RAG System for Indian Tax Law Research  
**Benchmark Reference**: 100 Real Government & Community Queries (`data/eval/real_queries_100.json`)  
**Status Date**: 2026-09-19  

---

## 1. Executive Overview

LexIndia is an authoritative, citation-grounded Retrieval-Augmented Generation (RAG) system built strictly for Indian Income Tax Law research. This document provides complete engineering and legal transparency regarding evaluation methodology, rubric evolutions, configuration boundaries, and items intentionally deferred for post-shipping iterations.

---

## 2. Evaluation Sample & Metric Provenance

### A. Headline Faithfulness: Stratified 50-Query Sample
- **Sample Selection**: The headline faithfulness score (**3.28 / 5.0**) is derived from a stratified **50-query sample** rather than the full 100-query benchmark.
- **Stratification Structure**:
  - **16 Regenerated Queries**: Specifically targets all previously flagged edge-case queries (`[2, 4, 8, 19, 21, 22, 23, 24, 25, 27, 28, 32, 36, 43, 52, 53]`) that suffered from early cache contamination or schedule-validation boundary issues.
  - **15 Cross-Family Spot-Check Queries**: Balanced across all 6 legal topics (`DEDUCTION`, `CALCULATION`, `TDS_TCS`, `CAPITAL_GAINS`, `PROCEDURE`, `REFUSAL`).
  - **10 Corrected Statutory Refusal Queries**: Covers queries requiring strict non-answer refusal under the cite-or-refuse policy.
  - **9 Standard Tax Research Queries**: Representing mainstream deduction and procedural queries.
- **Rationale**: Provider daily token-per-day (TPD) quota ceilings on Groq (`openai/gpt-oss-20b`, 200k daily ceiling) constrained live judging within a single 24-hour evaluation cycle. A stratified 50-query sample was accepted for final submission, with full 100-query Rubric v2 consistency deferred.

---

## 3. Dual Judge Rubric Evolution (Rubric v1 vs Rubric v2)

### A. The Rubric v1 Calibration Issue
During initial Phase 4 validation, the primary judge (`openai/gpt-oss-20b`) scored headline faithfulness at 1.93 / 5.0 despite Citation Accuracy reaching 85.9% and Refusal Precision reaching 100.0%. Forensic inspection revealed:
1. **Conflation of Helpfulness with Groundedness**: Under Rubric v1, the judge penalized faithful hedging statements (e.g., *"The retrieved context does not provide the specific turnover limit; please consult Section 44AB directly"*) with low scores (1/5 or 2/5).
2. **Disagreement with Cross-Family Judge**: On identical queries (such as Q39, Q41, Q56, and Q73), `gemini-3.5-flash-lite` awarded 5/5 for faithfully adhering to retrieved chunks without inventing ungrounded numbers, while `openai/gpt-oss-20b` awarded 1/5 for "failing to answer the taxpayer's question."

### B. Rubric v2 Specification
Rubric v2 explicitly decouples conversational helpfulness from legal faithfulness:
- **Core Principle**: Score *only* whether factual and legal claims in the answer are supported by retrieved statutory context chunks.
- **Hedging & Abstention Policy**: If an answer explicitly identifies that the retrieved statutory text lacks a specific numerical threshold or date and declines to guess, it is scored as **fully faithful (5/5)**.
- **Penalization**: Deductions apply strictly to hallucinations, fabricated section numbers, imagined tax rates, or ungrounded claims.

---

## 4. Configuration Split: Retrieval Tuning vs End-to-End Generation

In strict accordance with empirical research standards, LexIndia reports a clear separation between retrieval-layer tuning and end-to-end generation:

| Evaluation Component | Configuration Layer | Methodology & Parameters |
| :--- | :--- | :--- |
| **Retrieval Benchmark (Recall@K, MRR)** | **Post-Phase-3 Tuned** | Statutory Citation Boosting (regex `Section \d+` mapped to BM25 `must` clauses) + 5-Fold Cross-Validated Reciprocal Rank Fusion ($k=20$). Evaluated across all 85 answerable benchmark queries. |
| **End-to-End Generation Benchmark** | **Pre-Phase-3 Baseline Retrieval** | Evaluated under default RRF ($k=40$, top-8 chunks, 2-hop citation graph expansion) using `generator = qwen/qwen3.8-27b (live)`. |

> **Implication**: Because the generation layer already achieved **85.9% Citation Accuracy** and **100% Refusal Precision** under the baseline retrieval configuration, re-running end-to-end generation across the newly tuned retrieval pipeline (which elevated Recall@1 from 48.2% to 82.35% and MRR from 0.606 to 0.8646) would consume an additional ~250k generation tokens and is deferred to subsequent benchmark releases.

---

## 5. Model Ablation Status & Groq Quota Deferral

### A. Live Generation Model
- **Active Production Generator**: `qwen/qwen3.8-27b` (live via Groq). Fully evaluated across the 100-query benchmark with 0 fallback calls and full live telemetry.

### B. `openai/gpt-oss-120b` Comparison Status
- Initial canary testing confirmed high narrative depth with 120b. However, executing a live 53-query generation ablation (~127,000 tokens) against Groq's 8,000 TPM limit requires approximately 16–20 minutes of continuous paced execution.
- To avoid deployment blocking and rate-limit contention during project shipment, the full programmatic 120b ablation is cataloged in `ABLATION_TABLE.md` and deferred as future benchmarking work.

---

## 6. Deferred Roadmap Items for Future Releases

1. **Full 100-Query Rubric v2 Consistency**: Execute all 100 queries under Rubric v2 once provider 24-hour TPD limits reset.
2. **End-to-End Pipeline Evaluation on Tuned Retrieval**: Measure generation, citation, and faithfulness metrics when powered by the post-Phase-3 boosted retrieval configuration (Recall@1 82.35%, MRR 0.8646).
3. **Live 120b vs Qwen Programmatic Ablation**: Execute live token-matched generation comparison between `openai/gpt-oss-120b` and `qwen/qwen3.8-27b` without LLM judge calls.
4. **Elasticsearch Vector Optimization**: Dense HNSW vector indexing upgrades in Elasticsearch 8.11 for faster sub-10ms hybrid fusion latency.
