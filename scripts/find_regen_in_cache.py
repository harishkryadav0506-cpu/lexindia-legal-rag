import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

regen_ids = [2, 4, 8, 19, 21, 22, 23, 24, 25, 27, 28, 32, 36, 43, 52, 53]

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    eval_data = json.load(f)
qrs = {q["id"]: q for q in eval_data.get("query_results", [])}

cache_dir = Path("data/eval/cache/openai_gpt-oss-20b")
print("Searching cache files for the 16 regenerated queries...")

found = {}
for cf in cache_dir.glob("*.json"):
    try:
        with open(cf, "r", encoding="utf-8") as jf:
            cd = json.load(jf)
            prompt = cd.get("prompt", "")
            resp = cd.get("response", "")
            for qid in regen_ids:
                q_text = qrs[qid]["question"]
                if q_text in prompt:
                    m = re.search(r'"score"\s*:\s*(\d+)', resp)
                    reason_m = re.search(r'"reason"\s*:\s*"([^"]+)"', resp)
                    sc = int(m.group(1)) if m else None
                    re_str = reason_m.group(1) if reason_m else resp[:50]
                    is_v2 = "RUBRIC_V2" in prompt or cd.get("metadata", {}).get("rubric") == "v2"
                    found.setdefault(qid, []).append((cf.name[:8], sc, is_v2, re_str[:60]))
    except Exception:
        pass

for qid in regen_ids:
    entries = found.get(qid, [])
    print(f"Q{qid:02d}: {len(entries)} entries found: {entries}")
