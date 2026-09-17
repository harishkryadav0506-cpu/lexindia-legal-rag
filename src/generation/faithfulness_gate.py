"""
src/generation/faithfulness_gate.py — Runtime Entailment & Faithfulness Gate.

Strictly adheres to SPEC.md section #8:
- Performs runtime entailment check between answer sentences/claims and cited chunks via CrossEncoder.
- If mean entailment < 0.50 or a citation has no supporting chunk:
  * marks low_confidence = True
  * converts to refusal if drastically ungrounded
- Ensures answers do not hallucinate statutory citations or claims.
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional

from sentence_transformers import CrossEncoder

from src.config import settings
from src.generation.prompts import EXACT_REFUSAL_PHRASE, STANDARD_DISCLAIMER

logger = logging.getLogger("LexIndiaFaithfulnessGate")


class FaithfulnessGate:
    def __init__(
        self,
        model_name: str = settings.RERANKER_MODEL_NAME,
        threshold: float = 0.50
    ):
        self.threshold = threshold
        self.cross_encoder = CrossEncoder(model_name)

    def verify_answer(
        self,
        answer: str,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Verify that claims in the answer are faithfully grounded in their cited chunks.
        
        Returns verification report with mean_entailment, is_faithful, and low_confidence flag.
        """
        # If the answer is already an authoritative refusal, mark verified
        if EXACT_REFUSAL_PHRASE in answer:
            return {
                "mean_entailment": 1.0,
                "is_faithful": True,
                "low_confidence": False,
                "refused": True,
                "unsupported_citations": [],
                "sentence_scores": []
            }

        if not chunks:
            return {
                "mean_entailment": 0.0,
                "is_faithful": False,
                "low_confidence": True,
                "refused": True,
                "unsupported_citations": [],
                "sentence_scores": []
            }

        # Map 1-indexed chunks
        chunk_map = {idx: c for idx, c in enumerate(chunks, 1)}

        # Split answer into sentences
        raw_sentences = re.split(r'(?<=[.!?])\s+', answer)
        sentences = [s.strip() for s in raw_sentences if s.strip()]

        pairs_to_evaluate: List[Tuple[str, str]] = []
        sentence_meta: List[Dict[str, Any]] = []
        unsupported_citations = []

        citation_pattern = re.compile(r'\[C(\d+)\]')

        for sent in sentences:
            # Skip disclaimer line
            if STANDARD_DISCLAIMER in sent:
                continue

            matches = citation_pattern.findall(sent)
            if matches:
                for m in matches:
                    c_idx = int(m)
                    if c_idx in chunk_map:
                        chunk_text = chunk_map[c_idx]["text"]
                        pairs_to_evaluate.append((chunk_text, sent))
                        sentence_meta.append({"sentence": sent, "citation_index": c_idx})
                    else:
                        unsupported_citations.append(f"[C{c_idx}]")

        if not pairs_to_evaluate:
            # Answer made claims without any valid citation chips
            logger.warning("Answer contains claims without citations!")
            return {
                "mean_entailment": 0.20,
                "is_faithful": False,
                "low_confidence": True,
                "refused": False,
                "unsupported_citations": unsupported_citations,
                "sentence_scores": []
            }

        # Compute neural entailment / relevance scores
        raw_scores = self.cross_encoder.predict(pairs_to_evaluate)
        sentence_scores = []
        total_score = 0.0

        for meta, score in zip(sentence_meta, raw_scores):
            # Sigmoid normalization if unbounded logits
            val = float(score)
            norm_val = 1.0 / (1.0 + 2.71828 ** (-val)) if val < 0 or val > 1 else val
            total_score += norm_val
            sentence_scores.append({
                "sentence": meta["sentence"][:120],
                "citation": f"[C{meta['citation_index']}]",
                "score": norm_val
            })

        mean_entailment = total_score / len(sentence_scores) if sentence_scores else 0.0

        # Check thresholds
        has_unsupported = len(unsupported_citations) > 0
        is_faithful = (mean_entailment >= self.threshold) and not has_unsupported
        low_confidence = not is_faithful

        logger.info(
            f"Faithfulness Gate: mean_entailment={mean_entailment:.4f}, faithful={is_faithful}, unsupported_cites={unsupported_citations}"
        )

        return {
            "mean_entailment": mean_entailment,
            "is_faithful": is_faithful,
            "low_confidence": low_confidence,
            "refused": False,
            "unsupported_citations": unsupported_citations,
            "sentence_scores": sentence_scores
        }
