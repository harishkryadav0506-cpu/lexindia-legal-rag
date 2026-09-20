import json
from pathlib import Path

data = json.load(open('data/eval/eval_results.json', encoding='utf-8'))
qr = data['query_results']

low_scoring = []
for r in qr:
    pj = r.get('primary_judge')
    if pj and pj.get('score') is not None and pj.get('score') <= 2:
        low_scoring.append({
            "id": r['id'],
            "topic": r['topic'],
            "question": r['question'],
            "judge_score": pj.get('score'),
            "judge_reason": pj.get('reason'),
            "answer": r['answer'],
            "retrieved_context": r.get('retrieved_context', '')
        })

output_path = Path('data/eval/diagnostic_low_scoring.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(low_scoring, f, indent=2, ensure_ascii=False)

print(f"Dumped {len(low_scoring)} low scoring queries to {output_path}")
