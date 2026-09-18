"""
src/utils/llm_cache.py — Persistent response caching layer for evaluation runs.

Caches LLM completions under `data/eval/cache/<model_slug>/<prompt_hash>.json`
keyed by (model_id, prompt_sha256). Ensures reproducible evaluation metrics
and avoids re-consuming daily and minute rate limits on repeated runs.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any

CACHE_DIR = Path("data/eval/cache")


def _model_slug(model_id: str) -> str:
    return model_id.replace("/", "_").replace(":", "_").replace(".", "_")


def _prompt_hash(model_id: str, prompt: str) -> str:
    content = f"{model_id}::{prompt}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class LLMCache:
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, model_id: str, prompt: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response if it exists and contains valid content."""
        slug = _model_slug(model_id)
        phash = _prompt_hash(model_id, prompt)
        entry_path = self.cache_dir / slug / f"{phash}.json"
        if entry_path.exists():
            try:
                with open(entry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("response", "").strip():
                    return data
                else:
                    # Clean up empty cache file
                    entry_path.unlink(missing_ok=True)
            except Exception:
                return None
        return None

    def set(
        self,
        model_id: str,
        prompt: str,
        response_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store an LLM response with timestamp and execution metadata. Never caches empty strings."""
        if not response_text or not response_text.strip():
            return

        slug = _model_slug(model_id)
        phash = _prompt_hash(model_id, prompt)
        model_dir = self.cache_dir / slug
        model_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "model": model_id,
            "prompt_hash": phash,
            "response": response_text.strip(),
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        entry_path = model_dir / f"{phash}.json"
        with open(entry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def stats(self) -> Dict[str, int]:
        """Return counts of cached entries per model."""
        counts = {}
        if not self.cache_dir.exists():
            return counts
        for sub in self.cache_dir.iterdir():
            if sub.is_dir():
                counts[sub.name] = len(list(sub.glob("*.json")))
        return counts


llm_cache = LLMCache()
