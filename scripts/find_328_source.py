import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

# Check all 100 queries in eval_results.json
scores_100 = []
for q in d["query_results"]:
    pj = q.get("primary_judge") or {}
    sc = pj.get("score")
    if sc is not None:
        scores_100.append(sc)

print(f"Total non-null scores across all 100 queries: {len(scores_100)}")
print(f"Sum: {sum(scores_100)}, Mean: {sum(scores_100)/len(scores_100):.4f}")

# Check 72 queries
print(f"Mean across all {len(scores_100)} queries in eval_results.json = {sum(scores_100)/len(scores_100):.4f}")

# Check if 164 was produced anywhere
# If 164 was sum of 50 queries, 164 / 50 = 3.2800.
# If 169 was sum of 50 queries, 169 / 50 = 3.3800.
