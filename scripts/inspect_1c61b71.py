import subprocess
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

out = subprocess.check_output(["git", "show", "1c61b71:data/eval/eval_results.json"], encoding="utf-8")
d = json.loads(out)
qresults = {q["id"]: q for q in d.get("query_results", [])}

regen_ids = [2, 4, 8, 19, 21, 22, 23, 24, 25, 27, 28, 32, 36, 43, 52, 53] # 16
spot_ids = [1, 7, 14, 26, 31, 39, 41, 48, 56, 62, 69, 73, 81, 89, 95]     # 15
refusal_ids = [86, 87, 88, 90, 91, 92, 93, 94, 96, 97]                   # 10
standard_ids = [3, 5, 6, 9, 10, 12, 13, 15, 16]                          # 9

print("=== SCORES IN 1c61b71:data/eval/eval_results.json ===")
for name, ids in [
    ("(a) 16 Regenerated Queries", regen_ids),
    ("(b) 15 Spot-Check Queries", spot_ids),
    ("(c) 10 Corrected-Refusal Queries", refusal_ids),
    ("(d) 9 Standard Queries", standard_ids)
]:
    scores = []
    print(f"\n{name} (count: {len(ids)}):")
    for qid in ids:
        q = qresults.get(qid, {})
        pj = q.get("primary_judge") or {}
        sc = pj.get("score")
        reason = pj.get("reason", "")
        if sc is not None:
            scores.append(sc)
        print(f"  Q{qid:02d}: Score = {sc} | {reason[:60] if reason else 'None'}")
    if scores:
        print(f"  --> Mean: {sum(scores)/len(scores):.2f} (valid {len(scores)}/{len(ids)})")
    else:
        print(f"  --> All scores None")
