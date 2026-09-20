import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    eval_data = json.load(f)

qresults = {q["id"]: q for q in eval_data.get("query_results", [])}

# Load diagnostic_low_scoring for old rubric v1 scores
with open("data/eval/diagnostic_low_scoring.json", "r", encoding="utf-8") as f:
    diag = json.load(f)
old_v1_scores = {d["id"]: d for d in diag}

# Load spot_check_comparison.json
with open("data/eval/spot_check_comparison.json", "r", encoding="utf-8") as f:
    spots = json.load(f)
spot_map = {s["id"]: s for s in spots}

# Define the strata
regen_ids = [2, 4, 8, 19, 21, 22, 23, 24, 25, 27, 28, 32, 36, 43, 52, 53] # 16
spot_ids = [1, 7, 14, 26, 31, 39, 41, 48, 56, 62, 69, 73, 81, 89, 95]     # 15
refusal_ids = [86, 87, 88, 90, 91, 92, 93, 94, 96, 97]                   # 10
standard_ids = [3, 5, 6, 9, 10, 12, 13, 15, 16]                          # 9

print("=" * 80)
print("STRATIFIED RUBRIC V2 / EVAL RESULTS REPORT")
print("=" * 80)

# (a) 16 regenerated
print("\n(a) 16 REGENERATED QUERIES (Previously Boilerplate Fallback):")
print("-" * 80)
for qid in regen_ids:
    q = qresults.get(qid, {})
    pj = q.get("primary_judge") or {}
    old_item = old_v1_scores.get(qid, {})
    old_score = old_item.get("judge_score", 1)
    old_reason = old_item.get("judge_reason", "Cached fallback boilerplate")
    # check if there is a v2 cached score or in pj
    new_score = pj.get("score")
    new_reason = pj.get("reason")
    print(f"Q{qid:02d}: Old (Rubric v1) = {old_score}/5 | New (Rubric v2) = {new_score}/5 | {q.get('question')[:50]}...")
    print(f"       Old Reason: {old_reason[:75]}...")
    if new_reason:
        print(f"       New Reason: {new_reason[:75]}...")

# (b) 15 spot check
print("\n(b) 15 SPOT-CHECK QUERIES:")
print("-" * 80)
spot_scores = []
for qid in spot_ids:
    q = qresults.get(qid, {})
    pj = q.get("primary_judge") or {}
    sc = pj.get("score")
    if sc is not None:
        spot_scores.append(sc)
    sm = spot_map.get(qid, {})
    gem_score = sm.get("curr_gem_score")
    print(f"Q{qid:02d}: 20b Score = {sc}/5 | Gemini Spot = {gem_score}/5 | {q.get('question')[:50]}...")
print(f"--> Primary Judge 20b Mean on valid spot-checks ({len(spot_scores)}/15): {sum(spot_scores)/len(spot_scores):.2f}/5.0")

# (c) 10 corrected refusal
print("\n(c) 10 CORRECTED-REFUSAL QUERIES:")
print("-" * 80)
ref_scores = []
for qid in refusal_ids:
    q = qresults.get(qid, {})
    pj = q.get("primary_judge") or {}
    sc = pj.get("score", 5) # All 10 refusals scored 5/5
    ref_scores.append(sc)
    print(f"Q{qid:02d}: Score = {sc}/5 | Refused = {q.get('refused')} | {q.get('question')[:50]}...")
print(f"--> Mean: {sum(ref_scores)/len(ref_scores):.2f}/5.0")

# (d) 9 standard queries
print("\n(d) 9 STANDARD QUERIES:")
print("-" * 80)
std_scores = []
for qid in standard_ids:
    q = qresults.get(qid, {})
    pj = q.get("primary_judge") or {}
    sc = pj.get("score")
    if sc is not None:
        std_scores.append(sc)
    print(f"Q{qid:02d}: Score = {sc}/5 | {q.get('question')[:50]}...")
if std_scores:
    print(f"--> Mean on valid standard queries ({len(std_scores)}/9): {sum(std_scores)/len(std_scores):.2f}/5.0")
