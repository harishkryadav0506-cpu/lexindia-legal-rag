import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

qrs = {q["id"]: q for q in d["query_results"]}

# Strata definitions
regen_ids = [2, 4, 8, 19, 21, 22, 23, 24, 25, 27, 28, 32, 36, 43, 52, 53] # 16
spot_ids = [1, 7, 14, 26, 31, 39, 41, 48, 56, 62, 69, 73, 81, 89, 95]     # 15
refusal_ids = [86, 87, 88, 90, 91, 92, 93, 94, 96, 97]                   # 10
standard_ids = [3, 5, 6, 9, 10, 12, 13, 15, 16]                          # 9

print(f"Total queries across 4 strata: {len(regen_ids) + len(spot_ids) + len(refusal_ids) + len(standard_ids)}")

# Let's inspect spot_check_comparison.json
with open("data/eval/spot_check_comparison.json", "r", encoding="utf-8") as f:
    spot_data = json.load(f)
spot_map = {s["id"]: s for s in spot_data}

# Let's check the scores of each stratum
print("\n--- SPOT-CHECK 15 SCORES ---")
spot_p20b = []
spot_gem = []
for qid in spot_ids:
    s = spot_map.get(qid, {})
    p_sc = s.get("p20b_score")
    g_sc = s.get("curr_gem_score")
    spot_p20b.append(p_sc)
    spot_gem.append(g_sc)
    print(f"Q{qid:02d}: p20b={p_sc}, gemini={g_sc}, p20b_reason={str(s.get('p20b_reason'))[:50]}")

print(f"Spot 15 p20b valid scores: {[x for x in spot_p20b if x is not None]}")
print(f"Spot 15 p20b sum: {sum([x for x in spot_p20b if x is not None])}")
print(f"Spot 15 gemini valid scores: {[x for x in spot_gem if x is not None]}")
print(f"Spot 15 gemini mean: {sum([x for x in spot_gem if x is not None])/len([x for x in spot_gem if x is not None]):.4f}")

# Check 10 refusals
print("\n--- 10 REFUSALS ---")
ref_scores = []
for qid in refusal_ids:
    q = qrs.get(qid, {})
    # In Rubric v2, all unanswerable refusals get 5/5
    pj = q.get("primary_judge") or {}
    sc = pj.get("score")
    ref_scores.append(sc)
    print(f"Q{qid:02d}: score={sc}, reason={str(pj.get('reason'))[:50]}")

# Check 9 standard queries
print("\n--- 9 STANDARD QUERIES ---")
for qid in standard_ids:
    q = qrs.get(qid, {})
    pj = q.get("primary_judge") or {}
    print(f"Q{qid:02d}: score={pj.get('score')}, reason={str(pj.get('reason'))[:50]}")
