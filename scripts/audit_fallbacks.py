import json

with open("data/eval/eval_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

results = data.get("query_results", [])
refusals = [q for q in results if q.get("refused")]
answers = [q for q in results if not q.get("refused")]

offline_count = 0
live_count = 0

for a in answers:
    ans_text = a.get("answer", "")
    if "Subsequent guidance and rules indicate corresponding requirements under" in ans_text:
        offline_count += 1
    else:
        live_count += 1

print("--- GENERATION AUDIT (100 Queries Total) ---")
print(f"Total Refusal Queries (no LLM generation needed, exact statutory refusal): {len(refusals)}")
print(f"Total Answerable Queries (LLM generation requested): {len(answers)}")
print(f"  • Primary Model (Groq openai/gpt-oss-120b) successful calls: {live_count}")
print(f"  • Secondary/Offline Fallback calls (due to provider 429 quota exhaustion): {offline_count}")

# Check Judge Samples
judge_samples = data.get("judge_samples", [])
print(f"\n--- JUDGE AUDIT ({len(judge_samples)} Samples Evaluated) ---")
primary_live = 0
primary_fallback = 0
secondary_live = 0
secondary_fallback = 0

for s in judge_samples:
    p = s.get("primary_judge_gemini", {})
    sec = s.get("secondary_judge_groq", {})
    
    if "error" in p.get("reason", "").lower() or "missing" in p.get("reason", "").lower():
        primary_fallback += 1
    else:
        primary_live += 1
        
    if "quota exhausted" in sec.get("reason", "").lower() or "error" in sec.get("reason", "").lower() or "missing" in sec.get("reason", "").lower():
        secondary_fallback += 1
    else:
        secondary_live += 1

print(f"Primary Judge (Gemini gemini-3.5-flash / gemini-3.6-flash):")
print(f"  • Live completions: {primary_live}")
print(f"  • Fallback/quota default: {primary_fallback}")
print(f"Secondary Judge (Groq openai/gpt-oss-120b):")
print(f"  • Live completions: {secondary_live}")
print(f"  • Fallback/quota default: {secondary_fallback}")

if judge_samples:
    print("\nSample Primary Judge Record:")
    print(json.dumps(judge_samples[0]["primary_judge_gemini"], indent=2))
    print("\nSample Secondary Judge Record:")
    print(json.dumps(judge_samples[0]["secondary_judge_groq"], indent=2))
