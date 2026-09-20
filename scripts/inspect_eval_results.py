import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

qresults = {q["id"]: q for q in d["query_results"]}

regen_ids = [2, 4, 8, 19, 21, 22, 23, 24, 25, 27, 28, 32, 36, 43, 52, 53]
spot_ids = [1, 7, 14, 26, 31, 39, 41, 48, 56, 62, 69, 73, 81, 89, 95]
refusal_ids = [86, 87, 88, 90, 91, 92, 93, 94, 96, 97]
standard_ids = [3, 5, 6, 9, 10, 12, 13, 15, 16]

all_50 = regen_ids + spot_ids + refusal_ids + standard_ids
print(f"Total defined 50 queries: {len(all_50)}")

for name, ids in [
    ("(a) 16 Regenerated Queries", regen_ids),
    ("(b) 15 Spot-Check Queries", spot_ids),
    ("(c) 10 Corrected-Refusal Queries", refusal_ids),
    ("(d) 9 Standard Queries", standard_ids)
]:
    print(f"\n==========================================")
    print(f"{name} (count: {len(ids)}):")
    scores = []
    for qid in ids:
        q = qresults.get(qid, {})
        pj = q.get("primary_judge") or {}
        sc = pj.get("score")
        reason = pj.get("reason", "")
        # Also check if it's a refusal
        refused = q.get("refused", False)
        topic = q.get("topic", "")
        print(f"  Q{qid:02d}: Score = {sc} | Topic: {topic} | Refused: {refused} | Reason: {reason[:60] if reason else 'None'}")
        if sc is not None:
            scores.append(sc)
    if scores:
        print(f"  -> Scored count: {len(scores)}/{len(ids)}, Mean: {sum(scores)/len(scores):.2f}")
    else:
        print(f"  -> No non-null scores in primary_judge")
