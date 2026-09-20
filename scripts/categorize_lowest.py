import json, sys
sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open('data/eval/diagnostic_low_scoring.json', encoding='utf-8'))

print(f"Total low scoring items: {len(data)}\n")

categories = {
    "TRUNCATION": [],
    "HEDGING": [],
    "UNGROUNDED": [],
    "RUBRIC": []
}

# Inspect the 10 lowest scoring items
for idx, item in enumerate(data[:10], 1):
    qid = item['id']
    q = item['question']
    score = item['judge_score']
    reason = item['judge_reason']
    ans = item['answer']
    
    # Check truncation (cut mid sentence)
    is_truncated = not ans.rstrip().endswith((".", "*", "!", "?", "\"", "'", "}", ")")) or "..." in ans[-10:]
    
    # Check hedging (partial coverage / cannot answer)
    has_hedging = "cannot find" in ans.lower() or "cannot provide" in ans.lower() or "insufficient" in ans.lower() or "partial" in ans.lower()
    
    # Check rubric penalty vs ungrounded
    # E.g. in Q5, Q9: answer gives the real law (Rs 2,00,000 / Rs 1,50,000 / Rs 45 lakh) but context chunks were ITR validation rules rather than the Act section itself, so 20b penalized it as "not in context".
    print(f"--- #{idx}: Q{qid} [{item['topic']}] Score: {score}/5 ---")
    print(f"Question: {q}")
    print(f"Reason: {reason}")
    print(f"Answer length: {len(ans)} chars | Truncated flag: {is_truncated} | Hedging flag: {has_hedging}")
    print(f"Answer snippet: {repr(ans[:140])} ... {repr(ans[-100:])}\n")
