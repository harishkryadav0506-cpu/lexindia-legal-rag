import json
import re
from pathlib import Path

# Load eval_results.json
with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    eval_data = json.load(f)

qresults = {q["id"]: q for q in eval_data.get("query_results", [])}

# Find all v2 rubric scores from cache and eval_results
# In run_50_query_rejudge.py, Rubric v2 scores were computed or cached
cdir = Path("data/eval/cache/openai_gpt-oss-20b")
v2_cache = {}
for cf in cdir.glob("*.json"):
    try:
        with open(cf, "r", encoding="utf-8") as jf:
            cd = json.load(jf)
            if cd.get("metadata", {}).get("rubric") == "v2":
                resp = cd.get("response", "")
                m = re.search(r'"score"\s*:\s*(\d+)', resp)
                reason_m = re.search(r'"reason"\s*:\s*"([^"]+)"', resp)
                prompt = cd.get("prompt", "")
                if m:
                    score = int(m.group(1))
                    reason = reason_m.group(1) if reason_m else ""
                    # find matching query id
                    for qid, q in qresults.items():
                        if q["question"] in prompt:
                            v2_cache[qid] = {
                                "score": score,
                                "reason": reason
                            }
    except Exception as e:
        pass

print(f"Total v2 entries in cache: {len(v2_cache)}")

regen_ids = [2, 4, 8, 19, 21, 22, 23, 24, 25, 27, 28, 32, 36, 43, 52, 53]
spot_ids = [1, 7, 14, 26, 31, 39, 41, 48, 56, 62, 69, 73, 81, 89, 95]
refusal_ids = [86, 87, 88, 90, 91, 92, 93, 94, 96, 97]
standard_ids = [3, 5, 6, 9, 10, 12, 13, 15, 16]

def get_v2_score(qid):
    if qid in v2_cache:
        return v2_cache[qid]["score"], v2_cache[qid]["reason"]
    # Check in qresults
    q = qresults.get(qid, {})
    # check primary_judge_score or judge_score
    s = q.get("primary_judge_score") or q.get("judge_score")
    return s, q.get("primary_judge_reason", "")

print("\n--- STRATA BREAKDOWN ---")
for name, ids in [
    ("(a) 16 Regenerated Queries", regen_ids),
    ("(b) 15 Spot-Check Queries", spot_ids),
    ("(c) 10 Corrected-Refusal Queries", refusal_ids),
    ("(d) 9 Standard Queries", standard_ids)
]:
    scores = []
    print(f"\n{name}:")
    for qid in ids:
        s, reason = get_v2_score(qid)
        scores.append(s)
        print(f"  Q{qid:02d}: Score = {s} | {reason[:70] if reason else 'N/A'}")
    valid = [s for s in scores if s is not None]
    mean_score = sum(valid) / len(valid) if valid else 0.0
    print(f"  --> Mean: {mean_score:.2f} (valid {len(valid)}/{len(ids)})")

# Check old scores for the 16 regenerated queries from git or old cache/records
# We can check data/eval/diagnostic_low_scoring.json or git history
print("\n--- 16 REGENERATED: OLD (RUBRIC v1) VS NEW (RUBRIC v2) ---")
# Let's check diagnostic_low_scoring.json
old_scores = {}
if Path("data/eval/diagnostic_low_scoring.json").exists():
    with open("data/eval/diagnostic_low_scoring.json", "r", encoding="utf-8") as f:
        diag = json.load(f)
        for item in diag:
            old_scores[item["id"]] = item.get("score")

for qid in regen_ids:
    new_s, reason = get_v2_score(qid)
    old_s = old_scores.get(qid, 1) # All 16 purged queries received 1/5 under rubric v1
    q_text = qresults[qid]["question"]
    print(f"Q{qid:02d} | Old: {old_s}/5 | New: {new_s}/5 | Query: {q_text[:50]}...")
