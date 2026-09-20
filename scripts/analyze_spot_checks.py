import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.llm_cache import _prompt_hash, llm_cache
from src.config import settings

# Load current eval_results.json
curr_data = json.load(open('data/eval/eval_results.json', encoding='utf-8'))
curr_samples = {s['id']: s for s in curr_data.get('judge_samples', [])}

# Load last night's commit e6d7ca8 eval_results.json
prev_raw = subprocess.check_output(['git', 'show', 'e6d7ca8:data/eval/eval_results.json'], encoding='utf-8')
prev_data = json.loads(prev_raw)
prev_samples = {s['id']: s for s in prev_data.get('judge_samples', [])}
prev_qr = {r['id']: r for r in prev_data.get('query_results', [])}
curr_qr = {r['id']: r for r in curr_data.get('query_results', [])}

print(f"=== ANALYSIS OF 15 STRATIFIED SPOT-CHECK QUERIES ===")
print(f"Total current spot-check samples: {len(curr_samples)}")
print(f"Total prev spot-check samples: {len(prev_samples)}\n")

identical_answers = 0
differing_answers = 0

side_by_side = []

for qid in sorted(curr_samples.keys()):
    curr_s = curr_samples[qid]
    prev_s = prev_samples.get(qid, {})
    
    prev_ans = prev_qr[qid]['answer'].strip()
    curr_ans = curr_qr[qid]['answer'].strip()
    
    is_ans_identical = (prev_ans == curr_ans)
    if is_ans_identical:
        identical_answers += 1
    else:
        differing_answers += 1
        
    p20b_score = curr_s.get('primary_judge_groq_20b', {}).get('score')
    p20b_reason = curr_s.get('primary_judge_groq_20b', {}).get('reason')
    
    gem_score = curr_s.get('cross_family_gemini', {}).get('score')
    gem_reason = curr_s.get('cross_family_gemini', {}).get('reason')
    
    prev_gem_score = prev_s.get('cross_family_gemini', {}).get('score')
    
    # Check cache prompt hash
    ctx = curr_qr[qid].get('retrieved_context', '')
    prompt = f"QUESTION: {curr_qr[qid]['question']}\n\nRETRIEVED STATUTORY CONTEXT:\n{ctx}\n\nGENERATED LEGAL ANSWER:\n{curr_ans}\n\nRate Faithfulness (1-5) and provide your concise JSON output:"
    gem_hash = _prompt_hash(settings.JUDGE_CROSS_FAMILY, prompt)
    cache_entry = llm_cache.get(settings.JUDGE_CROSS_FAMILY, prompt)
    
    side_by_side.append({
        "id": qid,
        "topic": curr_s['topic'],
        "question": curr_qr[qid]['question'],
        "ans_identical": is_ans_identical,
        "prev_gem_score": prev_gem_score,
        "curr_gem_score": gem_score,
        "p20b_score": p20b_score,
        "p20b_reason": p20b_reason,
        "gem_reason": gem_reason,
        "gem_cached": cache_entry is not None,
        "gem_hash": gem_hash
    })

print(f"Answers comparison between last night and today:")
print(f"  • Identical answers: {identical_answers}/15")
print(f"  • Differing answers: {differing_answers}/15\n")

out_path = Path('data/eval/spot_check_comparison.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(side_by_side, f, indent=2, ensure_ascii=False)
print(f"Saved detailed side-by-side comparison to {out_path}")
