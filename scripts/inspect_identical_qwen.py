import json
from pathlib import Path

qwen_cache_dir = Path('data/eval/cache/qwen_qwen3_8-27b')
target_prefix = 'Based on the provided authoritative legal context for Financial Year 2024-25, he'

matching_files = []
for f in qwen_cache_dir.glob('*.json'):
    try:
        c = json.load(open(f, encoding='utf-8'))
        resp = c.get('response', '')
        if resp.startswith(target_prefix):
            matching_files.append((f, c))
    except Exception:
        pass

print(f"Total files with this exact response: {len(matching_files)}")
for f, c in matching_files[:3]:
    print(f"\nFile: {f.name}")
    print(f"Timestamp: {c.get('timestamp')}")
    print(f"Prompt preview: {repr(c.get('prompt', '')[:120])}")
    print(f"Metadata: {c.get('metadata')}")
