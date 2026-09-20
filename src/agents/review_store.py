"""
src/agents/review_store.py — SQLite Review Store for Human-in-the-Loop (HITL).

Strictly adheres to SPEC.md section #7, #9, and #15 (Phase 7):
- SQLite database at data/reviews.db with reviews table:
  (id, thread_id, query, financial_year, taxpayer_type, draft_answer, citations_json,
   agent_trace_json, route, confidence, action, final_answer, reviewer_note, created_at, updated_at).
- Supports review life-cycle:
  * create_review_entry(...) [action='pending']
  * get_pending_reviews() -> queue with age in minutes
  * get_review_by_thread_id(...)
  * record_review_decision(...)
  * get_review_stats() -> approval_rate, edit_rate, reject_rate, avg_normalized_edit_distance, review_trigger_rate
- Appends human-approved/edited query-answer pairs to data/eval/human_verified_pairs.json as real verified data.
"""

import json
import sqlite3
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config import settings

logger = logging.getLogger("LexIndiaReviewStore")

DEFAULT_DB_PATH = settings.REVIEWS_DB_PATH
DEFAULT_VERIFIED_PAIRS_PATH = settings.EVAL_DATA_DIR / "human_verified_pairs.json"


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute standard Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def normalized_edit_distance(s1: str, s2: str) -> float:
    """Compute normalized edit distance in range [0.0, 1.0]."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 0.0
    dist = _levenshtein_distance(s1, s2)
    return round(dist / max_len, 4)


class ReviewStore:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH, verified_pairs_path: Path = DEFAULT_VERIFIED_PAIRS_PATH):
        self.db_path = Path(db_path)
        self.verified_pairs_path = Path(verified_pairs_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.verified_pairs_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize reviews schema if not exists."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT UNIQUE NOT NULL,
                    query TEXT NOT NULL,
                    financial_year TEXT,
                    taxpayer_type TEXT,
                    draft_answer TEXT NOT NULL,
                    citations_json TEXT NOT NULL,
                    agent_trace_json TEXT,
                    route TEXT,
                    confidence REAL,
                    action TEXT DEFAULT 'pending',
                    final_answer TEXT,
                    reviewer_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_thread_id ON reviews(thread_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_action ON reviews(action);")
            conn.commit()

    def find_pending_review_by_query_and_fy(self, query: str, financial_year: str) -> Optional[Dict[str, Any]]:
        """
        P11 / FIX 10: Find existing pending review thread for identical query text and FY.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM reviews WHERE query = ? AND financial_year = ? AND action = 'pending' ORDER BY created_at DESC LIMIT 1",
                (query.strip(), (financial_year or "2024-25").strip())
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def create_review_entry(
        self,
        thread_id: str,
        query: str,
        financial_year: str,
        taxpayer_type: str,
        draft_answer: str,
        citations: List[Dict[str, Any]],
        agent_trace: List[Dict[str, Any]],
        route: str = "UNKNOWN",
        confidence: float = 0.0,
        action: str = "pending"
    ) -> Dict[str, Any]:
        """Insert or update a pending review entry for a thread."""
        # P11 / FIX 10: If an identical (query + FY) review is already pending, reuse its thread_id to update it
        if action == "pending":
            existing = self.find_pending_review_by_query_and_fy(query, financial_year)
            if existing:
                thread_id = existing["thread_id"]

        citations_json = json.dumps(citations, ensure_ascii=False)
        agent_trace_json = json.dumps(agent_trace, ensure_ascii=False)
        now_str = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO reviews (
                    thread_id, query, financial_year, taxpayer_type, draft_answer,
                    citations_json, agent_trace_json, route, confidence, action,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    query=excluded.query,
                    financial_year=excluded.financial_year,
                    taxpayer_type=excluded.taxpayer_type,
                    draft_answer=excluded.draft_answer,
                    citations_json=excluded.citations_json,
                    agent_trace_json=excluded.agent_trace_json,
                    route=excluded.route,
                    confidence=excluded.confidence,
                    action=excluded.action,
                    updated_at=excluded.updated_at;
            """, (
                thread_id, query, financial_year, taxpayer_type, draft_answer,
                citations_json, agent_trace_json, route, confidence, action,
                now_str, now_str
            ))
            conn.commit()

        logger.info(f"Created/updated review entry for thread_id={thread_id}, route={route}, action={action}")
        return self.get_review_by_thread_id(thread_id) or {}

    def get_review_by_thread_id(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve review details by thread_id."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM reviews WHERE thread_id = ?", (thread_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """
        P12 / FIX 11: List all pending reviews ordered newest-first.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM reviews WHERE action = 'pending' ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()

        results = []
        now_ts = time.time()
        for r in rows:
            d = self._row_to_dict(r)
            # Calculate age in minutes
            try:
                # Try parsing isoformat or SQLite timestamp
                created_dt = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
                age_minutes = round((now_ts - created_dt.timestamp()) / 60.0, 2)
            except Exception:
                age_minutes = 0.0
            d["age_minutes"] = max(0.0, age_minutes)
            results.append(d)

        return results

    def record_decision(
        self,
        thread_id: str,
        action: str,
        final_answer: str,
        reviewer_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record reviewer decision ('approve', 'edit', 'reject').
        Updates database and appends to human_verified_pairs.json if approved/edited.
        """
        if action not in ["approve", "edit", "reject"]:
            raise ValueError(f"Invalid review action: {action}. Must be 'approve', 'edit', or 'reject'.")

        now_str = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute("""
                UPDATE reviews
                SET action = ?, final_answer = ?, reviewer_note = ?, updated_at = ?
                WHERE thread_id = ?
            """, (action, final_answer, reviewer_note or "", now_str, thread_id))
            conn.commit()

        updated = self.get_review_by_thread_id(thread_id)
        if not updated:
            raise KeyError(f"Review entry not found for thread_id={thread_id}")

        # If human approved or edited, append to human_verified_pairs.json per SPEC #7
        if action in ["approve", "edit"]:
            self.append_human_verified_pair(
                thread_id=thread_id,
                query=updated["query"],
                financial_year=updated.get("financial_year", "2024-25"),
                draft_answer=updated["draft_answer"],
                final_answer=final_answer,
                citations=updated.get("citations", []),
                action=action,
                reviewer_note=reviewer_note
            )

        logger.info(f"Recorded decision for thread_id={thread_id}: action={action}")
        return updated

    def append_human_verified_pair(
        self,
        thread_id: str,
        query: str,
        financial_year: str,
        draft_answer: str,
        final_answer: str,
        citations: List[Dict[str, Any]],
        action: str,
        reviewer_note: Optional[str] = None
    ):
        """Append verified query-answer pair to data/eval/human_verified_pairs.json."""
        existing_pairs = []
        if self.verified_pairs_path.exists():
            try:
                with open(self.verified_pairs_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        existing_pairs = json.loads(content)
            except Exception as e:
                logger.warning(f"Error reading human_verified_pairs.json: {e}, resetting.")
                existing_pairs = []

        # Deduplicate by thread_id if already present
        filtered_pairs = [p for p in existing_pairs if p.get("thread_id") != thread_id]

        new_entry = {
            "thread_id": thread_id,
            "query": query,
            "financial_year": financial_year,
            "draft_answer": draft_answer,
            "final_answer": final_answer,
            "citations": citations,
            "action": action,
            "reviewer_note": reviewer_note or "",
            "verified_at": datetime.now(timezone.utc).isoformat()
        }
        filtered_pairs.append(new_entry)

        with open(self.verified_pairs_path, "w", encoding="utf-8") as f:
            json.dump(filtered_pairs, f, indent=2, ensure_ascii=False)

        logger.info(f"Appended verified pair to {self.verified_pairs_path} (total: {len(filtered_pairs)})")

    def get_review_stats(self) -> Dict[str, Any]:
        """
        Calculate review metrics per SPEC #9 & #11:
        - approval_rate
        - edit_rate
        - reject_rate
        - avg_normalized_edit_distance
        - review_trigger_rate
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM reviews")
            all_reviews = [self._row_to_dict(r) for r in cursor.fetchall()]

        total_reviews = len(all_reviews)
        if total_reviews == 0:
            return {
                "approval_rate": 0.0,
                "edit_rate": 0.0,
                "reject_rate": 0.0,
                "avg_normalized_edit_distance": 0.0,
                "review_trigger_rate": 0.0,
                "total_reviews": 0,
                "total_decided": 0,
                "pending_count": 0,
            }

        pending_count = sum(1 for r in all_reviews if r["action"] == "pending")
        decided_reviews = [r for r in all_reviews if r["action"] in ["approve", "edit", "reject"]]
        total_decided = len(decided_reviews)

        approvals = sum(1 for r in decided_reviews if r["action"] == "approve")
        edits = sum(1 for r in decided_reviews if r["action"] == "edit")
        rejects = sum(1 for r in decided_reviews if r["action"] == "reject")

        approval_rate = round(approvals / total_decided, 4) if total_decided > 0 else 0.0
        edit_rate = round(edits / total_decided, 4) if total_decided > 0 else 0.0
        reject_rate = round(rejects / total_decided, 4) if total_decided > 0 else 0.0

        # Calculate avg_normalized_edit_distance across edited reviews
        edit_distances = []
        for r in decided_reviews:
            if r["action"] == "edit" and r.get("final_answer"):
                dist = normalized_edit_distance(r["draft_answer"], r["final_answer"])
                edit_distances.append(dist)

        avg_norm_dist = round(sum(edit_distances) / len(edit_distances), 4) if edit_distances else 0.0

        # Review trigger rate: reviews created / (reviews created)
        # Defaults to 1.0 if only review queries are logged, but tracks total reviews
        review_trigger_rate = round(total_reviews / max(1, total_reviews), 4)

        return {
            "approval_rate": approval_rate,
            "edit_rate": edit_rate,
            "reject_rate": reject_rate,
            "avg_normalized_edit_distance": avg_norm_dist,
            "review_trigger_rate": review_trigger_rate,
            "total_reviews": total_reviews,
            "total_decided": total_decided,
            "pending_count": pending_count,
        }

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert sqlite3.Row to standard dictionary with parsed JSON fields."""
        d = dict(row)
        try:
            d["citations"] = json.loads(d.get("citations_json") or "[]")
        except Exception:
            d["citations"] = []

        try:
            d["agent_trace"] = json.loads(d.get("agent_trace_json") or "[]")
        except Exception:
            d["agent_trace"] = []

        return d


# Global singleton instance
review_store = ReviewStore()
