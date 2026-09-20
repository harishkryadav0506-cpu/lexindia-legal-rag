import json, re, sys
sys.path.insert(0, ".")
from pathlib import Path
from scripts.run_50_query_rejudge import SELECTED_50_IDS, SPOT_CHECK_15_IDS

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    eval_data = json.load(f)
qrs = {q["id"]: q for q in eval_data.get("query_results", [])}

# Find all v2 cache scores
cdir = Path("data/eval/cache/openai_gpt-oss-20b")
v2_scores = {}
for f in cdir.glob("*.json"):
    try:
        with open(f, "r", encoding="utf-8") as jf:
            d = json.load(jf)
            if d.get("metadata", {}).get("rubric") == "v2":
                resp = d.get("response", "")
                m = re.search(r'"score"\s*:\s*(\d+)', resp)
                if m:
                    # Match question in prompt
                    prompt = d.get("prompt", "")
                    for qid in SELECTED_50_IDS:
                        rec = qrs.get(qid)
                        if rec and rec["question"] in prompt:
                            v2_scores[qid] = {
                                "score": int(m.group(1)),
                                "reason": re.search(r'"reason"\s*:\s*"([^"]+)"', resp).group(1) if re.search(r'"reason"\s*:\s*"([^"]+)"', resp) else "",
                                "rubric": "v2"
                            }
    except Exception:
        pass

print(f"Direct Rubric v2 scores mapped: {len(v2_scores)}")
for qid in sorted(v2_scores.keys()):
    print(f"Q{qid:02d}: Score {v2_scores[qid]['score']} | {v2_scores[qid]['reason'][:60]}")

# Spot checks
with open("data/eval/spot_check_comparison.json", "r", encoding="utf-8") as f:
    spot_checks = json.load(f)
spot_map = {sc["id"]: sc for sc in spot_checks}

print("\nSpot check scores for 15 queries:")
gem_scores = []
for qid in SPOT_CHECK_15_IDS:
    sc = spot_map.get(qid)
    if sc and sc.get("curr_gem_score"):
        gem_scores.append(sc["curr_gem_score"])
        print(f"Q{qid:02d}: Gemini {sc['curr_gem_score']}/5 | p20b {sc.get('p20b_score')}/5")
print(f"Gemini 15 spot check mean: {sum(gem_scores)/len(gem_scores):.2f}")
