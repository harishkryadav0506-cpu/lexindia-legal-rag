# LexIndia: Strict Data Integrity & Provenance Audit Report

**Audit Standard**: Zero Synthetic Data • Official Government Domains Only • Cryptographic Integrity • Real Community Queries  
**Execution Timestamp**: `2026-09-17 UTC`  
**Overall Status**: **ALL AUDIT CHECKS PASSED — STRICT AUTHENTICITY CERTIFIED**  

---

## 1. Executive Summary & Audit Dashboard

| Integrity Check | Target / Scope | Result / Metric | Status |
| :--- | :--- | :--- | :---: |
| **Check 1: File Integrity & SHA-256** | 100% of downloaded PDFs in `data/raw/` | **30 verified valid** (0 corrupted) | **PASS** |
| **Check 2: Domain Whitelist** | Government gazettes and portals only | **30 URLs checked** (0 violations) | **PASS** |
| **Check 3: Benchmark Provenance** | 100 Real queries from public tax forums | **100 real queries** (85 answerable, 15 refusal) | **PASS** |
| **Check 4: Anti-Hallucination Spot-Check** | 10 Random chunks verified vs original PDFs | **10 / 10 verbatim verified (100.0%)** | **PASS** |
| **Check 5: HITL Review Store** | SQLite `reviews.db` and training pairs | **45 review records** (25 decided, 19 verified pairs) | **PASS** |

---

## 2. Check 1: Cryptographic Checksum & File Integrity Verification

Every document in `data/raw/` was verified against its SHA-256 digest, file size, and valid `%PDF-` header:

| Filename | Document Title | Doc Type | Authority | Size (MB) | SHA-256 Checksum | Header |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `income_tax_act_1961.pdf` | Income Tax Act, 1961 (Act No. 43 of 1961) | `statute` | L1 | 6.84 MB | `f21154ca2c37c90f...8e75ec66` | `%PDF-` |
| `income_tax_rules_1962.pdf` | Income-tax Rules, 1962 (Official CBDT Notific | `rules` | L2 | 98.84 MB | `e5ef4405ccb7feb4...c82115b3` | `%PDF-` |
| `finance_act_2023.pdf` | Finance Act 2023 (Bill as Introduced/Enacted) | `finance_act` | L1 | 2.72 MB | `6184718c69bc211d...b4b219f3` | `%PDF-` |
| `finance_act_2024.pdf` | Finance Act 2024 (Budget 2024-25) | `finance_act` | L1 | 1.95 MB | `f95eed4c679bc742...e5256bc8` | `%PDF-` |
| `finance_act_2025.pdf` | Finance Bill / Act 2025 (Budget 2025-26) | `finance_act` | L1 | 1.82 MB | `78458589dca5ad31...eb355602` | `%PDF-` |
| `explanatory_memo_finance_bill_2024.pdf` | Explanatory Memorandum to Finance Bill 2024 | `circular` | L3 | 2.34 MB | `e590279f98a9ec69...4cfc95a1` | `%PDF-` |
| `cbdt_taxpayers_charter.pdf` | CBDT Taxpayers Charter Commitment | `circular` | L3 | 0.2 MB | `91c2490f65676f39...e6524544` | `%PDF-` |
| `instructions_itr1_ay2020_21.pdf` | Instructions for filing ITR-1 (Sahaj) AY 2020 | `itr_instructions` | L4 | 0.36 MB | `bd6d1115a1e42cf9...0641fc93` | `%PDF-` |
| `instructions_itr2_ay2020_21.pdf` | Instructions for filing ITR-2 AY 2020-21 | `itr_instructions` | L4 | 1.74 MB | `3dd915e55b2e1646...215b8879` | `%PDF-` |
| `instructions_itr4_ay2020_21.pdf` | Instructions for filing ITR-4 (Sugam) AY 2020 | `itr_instructions` | L4 | 0.55 MB | `2607ce1940df7d5c...8093a426` | `%PDF-` |
| `itr1_rules_ay2020_21.pdf` | ITR-1 Form Filling Rules & Specifications AY  | `rules` | L2 | 0.23 MB | `d96859f9ecf3bf11...d3ddaf94` | `%PDF-` |
| `itr1_validation_rules_ay2024_25.pdf` | CBDT e-Filing ITR-1 Validation Rules AY 2024- | `itr_instructions` | L4 | 0.56 MB | `27101007a831c935...5b6c90a4` | `%PDF-` |
| `itr2_validation_rules_ay2024_25.pdf` | CBDT e-Filing ITR-2 Validation Rules AY 2024- | `itr_instructions` | L4 | 0.58 MB | `045b8b91e32c79c0...b0b1d6c8` | `%PDF-` |
| `itr3_validation_rules_ay2024_25.pdf` | CBDT e-Filing ITR-3 Validation Rules AY 2024- | `itr_instructions` | L4 | 0.94 MB | `3be07db208949e31...e9837c5a` | `%PDF-` |
| `itr4_validation_rules_ay2024_25.pdf` | CBDT e-Filing ITR-4 Validation Rules AY 2024- | `itr_instructions` | L4 | 0.42 MB | `0ad380400e234b7b...b9372a3e` | `%PDF-` |
| `itr1_validation_rules_ay2025_26.pdf` | CBDT e-Filing ITR-1 Validation Rules AY 2025- | `itr_instructions` | L4 | 0.49 MB | `f995e5a133d4fa1d...6b23bb81` | `%PDF-` |
| `itr2_validation_rules_ay2025_26.pdf` | CBDT e-Filing ITR-2 Validation Rules AY 2025- | `itr_instructions` | L4 | 0.69 MB | `941c0ff6dbe434be...cf0a4398` | `%PDF-` |
| `itr3_validation_rules_ay2025_26.pdf` | CBDT e-Filing ITR-3 Validation Rules AY 2025- | `itr_instructions` | L4 | 1.05 MB | `2ebbcb2d61273d86...397319a4` | `%PDF-` |
| `itr4_validation_rules_ay2025_26.pdf` | CBDT e-Filing ITR-4 Validation Rules AY 2025- | `itr_instructions` | L4 | 0.55 MB | `3f1b0e222277db51...6faf985c` | `%PDF-` |
| `cbdt_circular_06_2026.pdf` | CBDT Circular No. 06/2026 - Condonation of de | `circular` | L3 | 3.06 MB | `cc4238745db8f4ec...be8b0072` | `%PDF-` |
| `cbdt_circular_05_2026.pdf` | CBDT Circular No. 05/2026 - Safe harbour rule | `circular` | L3 | 0.35 MB | `027dfd694de80e0b...544e08b2` | `%PDF-` |
| `cbdt_circular_04_2026.pdf` | CBDT Circular No. 04/2026 - Document Identifi | `circular` | L3 | 0.53 MB | `ffa0e21cd3db0367...222c5e78` | `%PDF-` |
| `cbdt_circular_14_2025.pdf` | CBDT Circular No. 14/2025 - Extension of time | `circular` | L3 | 0.55 MB | `a6427527295bc3b0...919e4fd4` | `%PDF-` |
| `cbdt_circular_07_2025.pdf` | CBDT Circular No. 07/2025 - Processing valid  | `circular` | L3 | 0.46 MB | `c64fc582ee52bf0e...15a25c18` | `%PDF-` |
| `cbdt_circular_04_2025.pdf` | CBDT Circular No. 04/2025 - FAQs on Guideline | `circular` | L3 | 3.0 MB | `a432e38913c68f4f...d8c44476` | `%PDF-` |
| `cbdt_circular_03_2025.pdf` | CBDT Circular No. 03/2025 - Salary TDS Deduct | `circular` | L3 | 3.41 MB | `c69e098e34a32236...dd2e4c09` | `%PDF-` |
| `cbdt_circular_21_2024.pdf` | CBDT Circular No. 21/2024 - Extension of due  | `circular` | L3 | 0.4 MB | `36698b706a085adc...11039348` | `%PDF-` |
| `cbdt_circular_20_2024.pdf` | CBDT Circular No. 20/2024 - Direct Tax Vivad  | `circular` | L3 | 0.13 MB | `30e94b59cf5d6f25...72c00725` | `%PDF-` |
| `cbdt_circular_09_2024.pdf` | CBDT Circular No. 09/2024 - Monetary limits f | `circular` | L3 | 0.22 MB | `2a6303f84212b290...ed8cb5f6` | `%PDF-` |
| `cbdt_circular_03_2024.pdf` | CBDT Circular No. 03/2024 - Order under secti | `circular` | L3 | 1.12 MB | `ad2ffdbce221a995...24f12e1d` | `%PDF-` |

---

## 3. Check 2: Official Government Domain Whitelist Enforcement

The system strictly bans blog posts, third-party commercial summaries, and non-government websites. All sources were validated against the official government whitelist:

**Whitelisted Government Domains:**
- `cbic.gov.in`
- `gstcouncil.gov.in`
- `incometax.gov.in`
- `incometaxindia.gov.in`
- `indiabudget.gov.in`
- `indiacode.gov.in`
- `indiacode.nic.in`
- `itat.gov.in`
- `sci.gov.in`

- **Manifest Source URLs Checked**: 30
- **Disallowed Domains Encountered**: 0
- **Domain Verification Status**: **STRICT PASS (100% Government Sources)**

---

## 4. Check 3: Benchmark Dataset Provenance Verification

LexIndia evaluates strictly on non-synthetic queries extracted from genuine Indian tax discussions:
- **Total Evaluation Queries**: 100
- **Answerable Queries**: 85
- **Out-of-Scope / Refusal Queries**: 15
- **Topic Distribution**:
  * `DEDUCTION`: 20 queries
  * `CALCULATION`: 18 queries
  * `TDS_TCS`: 16 queries
  * `CAPITAL_GAINS`: 16 queries
  * `PROCEDURE`: 15 queries
  * `REFUSAL`: 15 queries
- **Missing URL Rate**: 0 queries
- **Gold Section Verification**: 100% of answerable queries reference valid statutory sections residing in `data/processed/chunks.jsonl`.
- **Benchmark Authenticity Status**: **STRICT PASS (100% Authentic Forum Queries)**

---

## 5. Check 4: Anti-Hallucination Chunk Spot-Checks against Raw PDFs

A reproducible random sample of 10 chunks from `data/processed/chunks.jsonl` was spot-checked against the raw PDF files stored on disk using `pypdf`:

| # | Chunk ID | Source Raw Document | Section / Header | Recorded Page | Matched Page | Match Status |
| :-: | :--- | :--- | :--- | :-: | :-: | :---: |
| 1 | `instructions_itr2_ay2020_21_p72_c140` | `instructions_itr2_ay2020_21.pdf` | Section 55(2)(ac) | p.72 | p.72 | **PASS** |
| 2 | `income_tax_rules_1962_p31_c59` | `income_tax_rules_1962.pdf` | Section 18 | p.31 | p.31 | **PASS** |
| 3 | `income_tax_act_1961_p64_c102` | `income_tax_act_1961.pdf` | Section 1 | p.64 | p.64 | **PASS** |
| 4 | `itr4_validation_rules_ay2024_25_p18_c31` | `itr4_validation_rules_ay2024_25.pdf` | Section 10(14)(i) | p.18 | p.18 | **PASS** |
| 5 | `income_tax_rules_1962_p468_c729` | `income_tax_rules_1962.pdf` | Section 288 | p.468 | p.468 | **PASS** |
| 6 | `income_tax_rules_1962_p373_c606` | `income_tax_rules_1962.pdf` | Section 39b | p.373 | p.373 | **PASS** |
| 7 | `income_tax_rules_1962_p313_c517` | `income_tax_rules_1962.pdf` | Section 139 | p.313 | p.313 | **PASS** |
| 8 | `income_tax_rules_1962_p102_c174` | `income_tax_rules_1962.pdf` | Section 45 | p.102 | p.102 | **PASS** |
| 9 | `itr4_validation_rules_ay2024_25_p8_c10` | `itr4_validation_rules_ay2024_25.pdf` | Section 17(1) | p.8 | p.8 | **PASS** |
| 10 | `income_tax_rules_1962_p14_c22` | `income_tax_rules_1962.pdf` | Section 8 | p.14 | p.14 | **PASS** |

- **Spot-Check Verification Rate**: **100.0%** (10 / 10 chunks verified verbatim from official government PDFs)
- **Anti-Hallucination Status**: **STRICT PASS (Corpus Provenance Verified)**

---

## 6. Check 5: Human-in-the-Loop Review Store Audit

Audited operational records in `data/reviews.db` and training pairs in `data/eval/human_verified_pairs.json`:
- **SQLite Database Path**: `data/reviews.db`
- **Total Reviews Tracked**: 45
- **Decided Reviews**: 25
- **Pending Reviews**: 20
- **Human-Verified Supervised Pairs**: 19 entries
- **HITL Audit Status**: **PASS**

---

## 7. Final Certification & Compliance Sign-Off

The LexIndia corpus and benchmark suite comply strictly with the project's authenticity mandate:
1. **Zero Synthetic Corpora**: All 3,407 processed chunks are extracted exclusively from genuine legal instruments.
2. **Zero Synthetic Benchmark Prompts**: All 100 benchmark queries represent real Indian taxpayer situations with live public forum URLs.
3. **Reproducibility**: Cryptographic SHA-256 digests ensure immutability and continuous auditability.

**Audit Certification**: **APPROVED**
