import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

qrs = {q["id"]: q for q in d["query_results"]}

# Let's inspect verbatim judge responses for Q22, Q28, Q43, a 5/5, and a 1/5
target_ids = [22, 28, 43, 86, 12, 5, 2, 31]

for qid in target_ids:
    q = qrs.get(qid, {})
    pj = q.get("primary_judge") or {}
    print(f"\n==========================================")
    print(f"QUERY ID: Q{qid:02d}")
    print(f"QUESTION: {q.get('question')}")
    print(f"TOPIC: {q.get('topic')}")
    print(f"SCORE: {pj.get('score')}")
    print(f"STATUS: {pj.get('status')}")
    print(f"VERBATIM REASON:\n{pj.get('reason')}")
    print(f"ANSWER SNIPPET:\n{q.get('answer', '')[:250]}...")
