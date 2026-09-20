import json
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

# Check 1c61b71:data/eval/eval_results.json
out = subprocess.check_output(["git", "show", "1c61b71:data/eval/eval_results.json"], encoding="utf-8")
d = json.loads(out)
qrs_1c = {q["id"]: q for q in d.get("query_results", [])}

# Check diagnostic_low_scoring.json
with open("data/eval/diagnostic_low_scoring.json", "r", encoding="utf-8") as f:
    diag = json.load(f)
diag_map = {x["id"]: x for x in diag}

for qid in [22, 28, 43]:
    print(f"\n==========================================")
    print(f"QUERY ID: Q{qid:02d}")
    if qid in qrs_1c:
        pj = qrs_1c[qid].get("primary_judge") or {}
        print(f"1c61b71 Score: {pj.get('score')}")
        print(f"1c61b71 Verbatim Reason:\n{pj.get('reason')}")
    if qid in diag_map:
        dm = diag_map[qid]
        print(f"diag_low Score: {dm.get('judge_score')}")
        print(f"diag_low Verbatim Reason:\n{dm.get('judge_reason')}")
