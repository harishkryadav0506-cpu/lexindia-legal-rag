import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

cdir = Path("data/eval/cache/openai_gpt-oss-20b")
v2_entries = []
for f in cdir.glob("*.json"):
    try:
        with open(f, "r", encoding="utf-8") as jf:
            d = json.load(jf)
            if d.get("metadata", {}).get("rubric") == "v2":
                v2_entries.append((f.name, d))
    except Exception:
        pass

print(f"Total Rubric v2 cache files: {len(v2_entries)}")
for fname, d in v2_entries:
    print(f"\nFile: {fname}")
    print(f"Response: {d.get('response')}")
