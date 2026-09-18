"""
Model Discovery & Verification Script for LexIndia
Pings live Groq and Google Gemini endpoints to identify active, supported models
and verifies their text generation capability.
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def verify_groq():
    print("==================================================")
    print("1. Groq Model Discovery (https://api.groq.com/openai/v1/models)")
    print("==================================================")
    if not GROQ_API_KEY:
        print("[!] GROQ_API_KEY is not configured.")
        return {}

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        resp = httpx.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=15.0)
        if resp.status_code != 200:
            print(f"[!] Groq /models error: {resp.status_code} - {resp.text}")
            return {}
        
        models_data = resp.json().get("data", [])
        verified_groq = {}
        for m in sorted(models_data, key=lambda x: x.get("id", "")):
            mid = m.get("id")
            active = m.get("active", True)
            ctx = m.get("context_window", 0)
            verified_groq[mid] = {"context_window": ctx, "active": active}
            print(f"  • {mid:<35} | context: {ctx:<7} | active: {active}")
        
        # Test generation with top candidates
        print("\nTesting Groq Live Inference:")
        for candidate in ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
            if candidate in verified_groq:
                payload = {
                    "model": candidate,
                    "messages": [{"role": "user", "content": "Ping test: respond with 'PONG'"}],
                    "max_tokens": 10
                }
                r = httpx.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=15.0)
                status = "SUCCESS" if r.status_code == 200 else f"FAIL ({r.status_code})"
                snippet = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip() if r.status_code == 200 else r.text[:80]
                print(f"  [{status}] {candidate} -> {snippet}")
        return verified_groq
    except Exception as e:
        print(f"[!] Error discovering Groq models: {e}")
        return {}


def verify_gemini():
    print("\n==================================================")
    print("2. Google Gemini Model Discovery (v1beta/models)")
    print("==================================================")
    if not GEMINI_API_KEY:
        print("[!] GEMINI_API_KEY is not configured.")
        return {}

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        resp = httpx.get(url, timeout=15.0)
        if resp.status_code != 200:
            print(f"[!] Gemini /models error: {resp.status_code} - {resp.text}")
            return {}

        models_list = resp.json().get("models", [])
        verified_gemini = {}
        for m in sorted(models_list, key=lambda x: x.get("name", "")):
            mid = m.get("name", "").replace("models/", "")
            methods = m.get("supportedGenerationMethods", [])
            in_limit = m.get("inputTokenLimit", 0)
            if "generateContent" in methods:
                verified_gemini[mid] = {"input_limit": in_limit, "display_name": m.get("displayName", "")}
                if any(k in mid for k in ["flash", "pro", "latest"]):
                    print(f"  • {mid:<35} | input_limit: {in_limit:<8} | name: {m.get('displayName')}")

        print("\nTesting Gemini Live Inference:")
        for candidate in ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]:
            call_url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={GEMINI_API_KEY}"
            r = httpx.post(call_url, json={"contents": [{"parts": [{"text": "Ping test: respond with 'PONG'"}]}]}, timeout=15.0)
            status = "SUCCESS" if r.status_code == 200 else f"FAIL ({r.status_code})"
            snippet = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() if r.status_code == 200 else r.text[:80]
            print(f"  [{status}] {candidate} -> {snippet}")
        return verified_gemini
    except Exception as e:
        print(f"[!] Error discovering Gemini models: {e}")
        return {}


if __name__ == "__main__":
    groq = verify_groq()
    gemini = verify_gemini()
    print("\n==================================================")
    print("Recommended Production Roles:")
    print("  GENERATION_MODEL: openai/gpt-oss-120b (Groq, 131,072 context)")
    print("  EXPANSION_MODEL:  qwen/qwen3.8-27b    (Groq, 131,042 context)")
    print("  JUDGE_PRIMARY:    gemini-3.5-flash    (Google GenAI, 1,048,576 context)")
    print("  FALLBACK_PRIMARY: gemini-flash-latest (Google GenAI, 1,048,576 context)")
    print("==================================================")
