import subprocess, json

output = subprocess.check_output(['git', 'show', 'e6d7ca8:data/eval/eval_results.json'], encoding='utf-8')
data = json.loads(output)
qr = data['query_results']

print('Checking commit e6d7ca8 (last night commit):')
for qid in [2, 19, 21, 22, 23, 24]:
    q = next(r for r in qr if r['id'] == qid)
    print(f"Q{qid}: {q['question']}")
    print(f"   Answer: {q['answer'][:90]}...\n")
