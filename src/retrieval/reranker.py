"""
src/retrieval/reranker.py — Neural Cross-Encoder Reranking with Statutory Authority Weighting.

Strictly adheres to SPEC.md section #6:
- Uses BAAI/bge-reranker-base over fused top candidate chunks (e.g. top 30).
- Returns top 8 chunks with rerank scores.
- Implements mandatory authority weighting:
  final_score = rerank_score * weight
  weights = {1: 1.0, 2: 0.95, 3: 0.85, 4: 0.6}
  (1=Act, 2=Rules, 3=Circular/Notification, 4=Instructions)
"""

import logging
from typing import List, Dict, Any, Optional

from sentence_transformers import CrossEncoder

from src.config import settings

logger = logging.getLogger("LexIndiaReranker")

AUTHORITY_WEIGHTS: Dict[int, float] = {
    1: 1.0,   # Statute / Act
    2: 0.95,  # Rules
    3: 0.85,  # Circulars / Notifications
    4: 0.60,  # ITR Instructions / Guidance
}


class Reranker:
    def __init__(
        self,
        model_name: str = settings.RERANKER_MODEL_NAME,
        model: Optional[CrossEncoder] = None
    ):
        self.model_name = model_name
        self.model = model or CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using CrossEncoder and apply authority weighting.
        
        Returns top_n chunks sorted by final_score descending.
        """
        if not candidates:
            return []

        # Prepare sentence pairs for cross-encoder
        pairs = [(query, c["text"]) for c in candidates]
        raw_scores = self.model.predict(pairs)

        reranked_chunks = []
        for chunk, score in zip(candidates, raw_scores):
            item = dict(chunk)
            # Normalize or record raw rerank score
            rerank_score = float(score)
            auth_level = item.get("authority_level", 4)
            weight = AUTHORITY_WEIGHTS.get(auth_level, 0.60)
            final_score = rerank_score * weight

            item["rerank_score"] = rerank_score
            item["authority_weight"] = weight
            item["final_score"] = final_score
            item["graph_expanded"] = False  # Base retrieved chunks are not graph expanded

            reranked_chunks.append(item)

        # Sort by final weighted score descending
        reranked_chunks.sort(key=lambda x: x["final_score"], reverse=True)
        top_results = reranked_chunks[:top_n]

        logger.info(
            f"Reranked {len(candidates)} chunks -> selected top {len(top_results)} (highest score: {top_results[0]['final_score']:.4f})"
        )
        return top_results
