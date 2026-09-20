import json
from pathlib import Path

qwen_cache_dir = Path('data/eval/cache/qwen_qwen3_8-27b')
print(f"Total qwen cache files: {len(list(qwen_cache_dir.glob('*.json')))}")

# Inspect cache files in qwen cache
responses = {}
for f in qwen_cache_dir.glob('*.json'):
    try:
        c = json.load(open(f, encoding='utf-8'))
        resp = c.get('response', '')
        pref = resp[:80]
        responses[pref] = responses.get(pref, 0) + 1
    except Exception:
        pass

for pref, count in sorted(responses.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"Count {count}: {repr(pref)}")
