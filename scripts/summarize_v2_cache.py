import json, re
from pathlib import Path

cdir = Path("data/eval/cache/openai_gpt-oss-20b")
v2_files = []
for f in cdir.glob("*.json"):
    try:
        with open(f, "r", encoding="utf-8") as jf:
            d = json.load(jf)
            if d.get("metadata", {}).get("rubric") == "v2":
                v2_files.append((f, d))
    except Exception:
        pass

print(f"Total Rubric v2 cache files: {len(v2_files)}")
scores = []
for f, d in v2_files:
    resp = d.get("response", "")
    m = re.search(r'"score"\s*:\s*(\d+)', resp)
    if m:
        score = int(m.group(1))
        scores.append(score)
        clean_resp = resp.encode("ascii", errors="replace").decode("ascii")
        print(f"{f.name[:10]}: score={score}/5 | {clean_resp[:70]}")

if scores:
    print(f"\nAverage score across {len(scores)} v2 evaluations: {sum(scores)/len(scores):.2f} / 5.0")
