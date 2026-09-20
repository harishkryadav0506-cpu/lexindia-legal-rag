import subprocess
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

for commit in ["e6d7ca8", "1c61b71", "HEAD"]:
    try:
        out = subprocess.check_output(["git", "show", f"{commit}:data/eval/eval_results.json"], encoding="utf-8")
        d = json.loads(out)
        s = d.get("summary", {})
        print(f"Commit {commit}:")
        print(f"  judge_agreement: {s.get('judge_agreement')}")
        print(f"  faithfulness_mean_50_queries: {s.get('faithfulness_mean_50_queries')}")
        print(f"  call_attribution primary_judge: {s.get('call_attribution', {}).get('primary_judge')}")
    except Exception as e:
        print(f"Commit {commit}: {e}")
