import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

qrs = {q["id"]: q for q in d["query_results"]}

regen_ids = [2, 4, 8, 19, 21, 22, 23, 24, 25, 27, 28, 32, 36, 43, 52, 53] # 16
spot_ids = [1, 7, 14, 26, 31, 39, 41, 48, 56, 62, 69, 73, 81, 89, 95]     # 15
refusal_ids = [86, 87, 88, 90, 91, 92, 93, 94, 96, 97]                   # 10
standard_ids = [3, 5, 6, 9, 10, 12, 13, 15, 16]                          # 9

all_50 = regen_ids + spot_ids + refusal_ids + standard_ids

print("=== RAW eval_results.json SCORES ===")
for name, ids in [
    ("Regenerated (16)", regen_ids),
    ("Spot Check (15)", spot_ids),
    ("Corrected Refusal (10)", refusal_ids),
    ("Standard (9)", standard_ids)
]:
    print(f"\n--- {name} ---")
    for qid in ids:
        q = qrs[qid]
        pj = q.get("primary_judge") or {}
        sc = pj.get("score")
        st = pj.get("status")
        print(f"Q{qid:02d}: score={sc}, status={st}")
