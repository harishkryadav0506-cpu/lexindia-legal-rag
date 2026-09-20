import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

qrs = {q["id"]: q for q in d["query_results"]}

SELECTED_50_IDS = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    12, 13, 14, 15, 16, 19, 21, 22, 23, 24,
    25, 26, 27, 28, 31, 32, 36, 39, 41, 43,
    48, 52, 53, 56, 62, 69, 73, 81,
    86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97
]

scored_items = []
for qid in SELECTED_50_IDS:
    pj = (qrs[qid].get("primary_judge") or {})
    sc = pj.get("score")
    if sc is not None:
        scored_items.append((qid, sc, pj.get("reason", "")))
        print(f"Q{qid:02d}: Score = {sc}/5 | {pj.get('reason', '')[:70]}")

print(f"\nTotal scored: {len(scored_items)}")
scores = [s for q, s, r in scored_items]
print(f"Sum of scores: {sum(scores)}")
print(f"Mean of available scored: {sum(scores)/len(scores):.4f}")
