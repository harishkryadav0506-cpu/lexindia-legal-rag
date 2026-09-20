import json
from pathlib import Path

data = json.load(open('data/eval/eval_results.json', encoding='utf-8'))
qr = data['query_results']

low_scoring = []
for r in qr:
    pj = r.get('primary_judge')
    if pj and pj.get('score') is not None and pj.get('score') <= 2:
        low_scoring.append(r)

print(f"Total low scoring queries (score <= 2): {len(low_scoring)}")
for i, r in enumerate(low_scoring[:10], 1):
    pj = r['primary_judge']
    print(f"\n{'='*70}")
    print(f"ITEM {i}: Query #{r['id']} [{r['topic']}] — Score: {pj.get('score')}/5")
    print(f"Question: {r['question']}")
    print(f"Judge Reason: {pj.get('reason')}")
    print(f"Full Answer Text:\n{r['answer']}")
