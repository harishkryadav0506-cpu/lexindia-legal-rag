import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

qrs = {q["id"]: q for q in d["query_results"]}

SELECTED_50_IDS = [
    # 10 Standard / Baseline queries
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    # Additional Standard & Spot-check queries
    12, 13, 14, 15, 16, 19, 21, 22, 23, 24,
    25, 26, 27, 28, 31, 32, 36, 39, 41, 43,
    48, 52, 53, 56, 62, 69, 73, 81,
    # 12 Corrected Statutory Refusal queries
    86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97
]

print(f"SELECTED_50_IDS length: {len(SELECTED_50_IDS)}")

# Let's inspect each of the 50 queries in eval_results.json
present_scores = {}
missing = []
for qid in SELECTED_50_IDS:
    q = qrs.get(qid)
    pj = (q.get("primary_judge") or {})
    sc = pj.get("score")
    if sc is not None:
        present_scores[qid] = sc
    else:
        missing.append(qid)

print(f"Scored queries in eval_results.json among the 50: {len(present_scores)}")
print(f"Missing queries among the 50: {len(missing)} -> {missing}")

# Now let's check judge_samples in eval_results.json
print("\n--- JUDGE SAMPLES IN EVAL_RESULTS.JSON ---")
jsamples = d.get("judge_samples", [])
print(f"Total judge_samples: {len(jsamples)}")
sample_scores = {}
for s in jsamples:
    qid = s.get("id")
    p_sc = (s.get("primary_judge_groq_20b") or {}).get("score")
    g_sc = (s.get("cross_family_gemini") or {}).get("score")
    sample_scores[qid] = (p_sc, g_sc)
    print(f"Sample Q{qid:02d}: p20b={p_sc}, gemini={g_sc}")
