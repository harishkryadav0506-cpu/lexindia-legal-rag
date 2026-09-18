import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

groq_key = os.getenv("GROQ_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

print("--- CANARY 1: GROQ (qwen/qwen3.8-27b) ---")
groq_url = "https://api.groq.com/openai/v1/chat/completions"
groq_headers = {
    "Authorization": f"Bearer {groq_key}",
    "Content-Type": "application/json"
}
groq_payload = {
    "model": "qwen/qwen3.8-27b",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 1
}

groq_resp = httpx.post(groq_url, headers=groq_headers, json=groq_payload, timeout=20.0)
print(f"HTTP Status: {groq_resp.status_code}")
try:
    groq_json = groq_resp.json()
    print("Response JSON:")
    print(json.dumps(groq_json, indent=2))
    print(f"Server returned model field: {groq_json.get('model')}")
except Exception as e:
    print(f"Response text: {groq_resp.text}")

print("\n--- CANARY 2: GOOGLE GENAI (gemini-3.6-flash) ---")
gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={gemini_key}"
gemini_payload = {
    "contents": [{"parts": [{"text": "hi"}]}],
    "generationConfig": {"maxOutputTokens": 1}
}
gemini_resp = httpx.post(gemini_url, json=gemini_payload, timeout=20.0)
print(f"HTTP Status: {gemini_resp.status_code}")
try:
    gemini_json = gemini_resp.json()
    print("Response JSON:")
    print(json.dumps(gemini_json, indent=2))
    print(f"Server returned model field / modelVersion: {gemini_json.get('modelVersion')}")
except Exception as e:
    print(f"Response text: {gemini_resp.text}")
