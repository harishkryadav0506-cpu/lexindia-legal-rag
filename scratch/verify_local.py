import urllib.request
import json
import sys

print("Checking initial review queue count...")
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/reviews/pending", timeout=15) as r:
        init_pending = json.loads(r.read())
    init_count = len(init_pending)
    print(f"Initial pending count: {init_count}")
except Exception as e:
    print(f"Error fetching pending: {e}")
    sys.exit(1)

print("\nRunning Query D: 'What is the deduction limit under Section 80C?' with require_review=True...")
payload_d = json.dumps({
    "question": "What is the deduction limit under Section 80C?",
    "require_review": True
}).encode("utf-8")

req_d = urllib.request.Request(
    "http://127.0.0.1:8000/query",
    data=payload_d,
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(req_d, timeout=120) as r:
    data_d = json.loads(r.read())

print("Query D status:", data_d.get("status"))
print("Query D review_required:", data_d.get("review_required"))
answer_d = data_d.get("draft_answer") or data_d.get("answer") or data_d.get("final_answer") or ""
print("Query D answer length:", len(answer_d))
print("Query D answer tail:\n", repr(answer_d[-250:]))
print("Query D ends cleanly without mid-sentence truncation:", bool(answer_d and answer_d.strip()[-1] in ".!?*)\"'"))

print("\nChecking updated review queue count...")
with urllib.request.urlopen("http://127.0.0.1:8000/reviews/pending", timeout=15) as r:
    new_pending = json.loads(r.read())
new_count = len(new_pending)
print(f"New pending count: {new_count} (Incremented: {new_count > init_count}, diff = {new_count - init_count})")

print("\nRunning Query E: 'How do I file taxes in USA?' with require_review=False...")
payload_e = json.dumps({
    "question": "How do I file taxes in USA?",
    "require_review": False
}).encode("utf-8")

req_e = urllib.request.Request(
    "http://127.0.0.1:8000/query",
    data=payload_e,
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(req_e, timeout=120) as r:
    data_e = json.loads(r.read())

print("Query E status:", data_e.get("status"))
print("Query E refused:", data_e.get("refused"))
print("Query E citations count:", len(data_e.get("citations", [])))
print("Query E answer:\n", data_e.get("final_answer") or data_e.get("answer"))
