import json, hashlib, sys
sys.path.insert(0, ".")
from pathlib import Path
from scripts.run_50_query_rejudge import SELECTED_50_IDS
from src.evaluation.llm_judge import JUDGE_SYSTEM_PROMPT, _parse_judge_json

with open('data/eval/eval_results.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
qrs = {q['id']: q for q in d.get('query_results', [])}

cache_dir = Path('data/eval/cache/openai_gpt-oss-20b')

v2_cached = []
for qid in SELECTED_50_IDS:
    rec = qrs.get(qid)
    if not rec:
        continue
    user_prompt = f"""QUESTION: {rec['question']}

RETRIEVED STATUTORY CONTEXT:
{rec.get('retrieved_context', '')}

GENERATED LEGAL ANSWER:
{rec.get('answer', '')}

Rate Faithfulness (1-5) and provide your concise JSON output:"""
    cprompt = f"RUBRIC_V2::{JUDGE_SYSTEM_PROMPT}::{user_prompt}"
    key = hashlib.sha256(cprompt.encode('utf-8')).hexdigest()
    fpath = cache_dir / f"{key}.json"
    if fpath.exists():
        with open(fpath, 'r', encoding='utf-8') as cf:
            cdata = json.load(cf)
            res = _parse_judge_json(cdata.get("content", ""))
            v2_cached.append((qid, res.get("score"), res.get("reason", "")))

print(f"V2 Cached count: {len(v2_cached)} / 50")
scores = [s for q, s, r in v2_cached if s is not None]
if scores:
    print(f"Average score of V2 cached: {sum(scores)/len(scores):.2f}")
for q, s, r in v2_cached:
    print(f"Q{q:02d}: Score {s}/5 | {r[:60]}")
