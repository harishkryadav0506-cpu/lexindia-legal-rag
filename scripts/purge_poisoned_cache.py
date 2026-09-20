import json
from pathlib import Path

cache_root = Path('data/eval/cache')

poisoned_snippets = [
    "regarding the availability of the standard deduction under Section 16(ia) for salaried employees",
    "regarding the deductibility of employer contributions to the National Pension System (NPS)",
    "under Section 115BAC (New Tax Regime) versus the Old Tax Regime",
    "Under the provisions of **Section 2** of the Explanatory Memorandum to Finance Bill 2024"
]

purged_files = []

for d in cache_root.iterdir():
    if not d.is_dir():
        continue
    for f in d.glob('*.json'):
        try:
            data = json.load(open(f, encoding='utf-8'))
            resp = data.get('response', '')
            # If the response itself is poisoned boilerplate
            is_poisoned = any(snip in resp for snip in poisoned_snippets)
            if is_poisoned:
                f.unlink(missing_ok=True)
                purged_files.append((d.name, f.name, "poisoned generation response"))
        except Exception:
            pass

# Also purge any judge entries in openai_gpt-oss-20b or gemini that evaluated these poisoned answers
# Since judge prompt contains the answer text, we can detect it in prompt or response!
# Note: judge entries don't store prompt text by default, but we will re-judge anyway.

print(f"Total poisoned cache entries purged: {len(purged_files)}")
for dname, fname, reason in purged_files:
    print(f"  Purged [{dname}]: {fname}")
