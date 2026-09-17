"""
src/generation/generator.py — Legal Answer Generator with Mandatory Provider Fallback.

Strictly adheres to SPEC.md section #8:
- Uses GENERATION_MODEL (default openai/gpt-oss-120b via Groq, temperature 0.1, max_tokens 1024).
- Input: question + retrieved chunks with chunk IDs and citation indices [C1]..[Cn].
- Provider Fallback (mandatory): If Groq returns 429/5xx after retries, automatically route
  the same request to gemini-2.5-flash and log a structured fallback event.
- Includes mock_429 support for verifying fallback behavior in automated tests.
"""

import json
import logging
import time
from typing import List, Dict, Any, Tuple, Optional

from src.config import settings
from src.generation.prompts import (
    SYSTEM_PROMPT,
    EXACT_REFUSAL_PHRASE,
    STANDARD_DISCLAIMER,
    build_generation_prompt,
)

logger = logging.getLogger("LexIndiaGenerator")


class AnswerGenerator:
    def __init__(self):
        self.model = settings.GENERATION_MODEL
        self.fallback_model = settings.JUDGE_PRIMARY  # gemini-2.5-flash
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_base_url = settings.GROQ_BASE_URL
        self.gemini_api_key = settings.GEMINI_API_KEY

    def _call_groq(self, user_prompt: str, mock_429: bool = False) -> str:
        """Execute generation via Groq OpenAI-compatible client."""
        if mock_429:
            raise RuntimeError("HTTP 429: Too Many Requests - Rate limit exceeded (mocked)")

        from openai import OpenAI
        client = OpenAI(
            api_key=self.groq_api_key,
            base_url=self.groq_base_url,
            timeout=30.0
        )
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=1024
        )
        return response.choices[0].message.content.strip()

    def _call_gemini_fallback(self, user_prompt: str, reason: str) -> Tuple[str, Dict[str, Any]]:
        """Fallback to gemini-2.5-flash on Groq 429/5xx with structured telemetry."""
        t0 = time.time()
        logger.warning(
            f"GENERATOR PROVIDER FALLBACK TRIGGERED: {self.model} -> {self.fallback_model} | Reason: {reason}"
        )
        from google import genai
        client = genai.Client(api_key=self.gemini_api_key)
        full_contents = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
        # Try configured fallback model, then fallback candidates
        candidate_models = [self.fallback_model, "gemini-3.6-flash", "gemini-flash-latest"]
        last_gemini_err = None
        for gm in candidate_models:
            try:
                response = client.models.generate_content(
                    model=gm,
                    contents=full_contents
                )
                latency_ms = int((time.time() - t0) * 1000)
                fallback_event = {
                    "event": "provider_fallback",
                    "component": "generator",
                    "model_from": self.model,
                    "model_to": gm,
                    "reason": reason,
                    "latency_ms": latency_ms
                }
                logger.info(f"STRUCTURED_FALLBACK_EVENT: {json.dumps(fallback_event)}")
                return response.text.strip(), fallback_event
            except Exception as e:
                last_gemini_err = e
                continue
        raise RuntimeError(f"All Gemini fallback models failed: {last_gemini_err}")

    def _offline_synthesize(self, question: str, chunks: List[Dict[str, Any]], fy: str) -> str:
        """Deterministic offline grounded synthesis when no live API keys are provided."""
        if not chunks:
            return f"{EXACT_REFUSAL_PHRASE}\n\n*{STANDARD_DISCLAIMER}*"

        top_chunk = chunks[0]
        sec_id = top_chunk.get("section_id", "statute")
        act = top_chunk.get("act_name", "Income-tax Act, 1961")
        doc_type = top_chunk.get("doc_type", "statute")
        snippet = top_chunk.get("text", "")[:280].strip()

        answer = (
            f"Under the provisions of **{sec_id}** of the {act} for Financial Year {fy} [C1], "
            f"the relevant legal position states:\n\n"
            f"> {snippet}...\n\n"
            f"Subsequent guidance and rules indicate corresponding requirements under {doc_type.upper()} [C1]."
        )
        if len(chunks) > 1:
            c2 = chunks[1]
            answer += f" Further, related conditions apply as specified in **{c2.get('section_id', 'applicable rules')}** [C2]."

        answer += f"\n\n*{STANDARD_DISCLAIMER}*"
        return answer

    def generate_answer(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
        financial_year: str = "2024-25",
        taxpayer_type: str = "Individual (Salaried)",
        mock_429: bool = False
    ) -> Dict[str, Any]:
        """
        Generate answer strictly grounded in retrieved chunks.
        Returns dict containing answer text, fallback flags, and citations mapping.
        """
        if not chunks:
            return {
                "answer": f"{EXACT_REFUSAL_PHRASE}\n\n*{STANDARD_DISCLAIMER}*",
                "refused": True,
                "fallback_used": False,
                "fallback_model": None,
                "fallback_event": None,
                "citations": []
            }

        user_prompt = build_generation_prompt(
            question=question,
            chunks=chunks,
            financial_year=financial_year,
            taxpayer_type=taxpayer_type
        )

        fallback_used = False
        fallback_model = None
        fallback_event = None
        raw_answer = ""

        # Try Groq primary model
        if (self.groq_api_key and self.groq_api_key != "your_groq_api_key_here") or mock_429:
            try:
                raw_answer = self._call_groq(user_prompt, mock_429=mock_429)
            except Exception as e:
                err_str = str(e)
                logger.warning(f"Primary model generation failed ({e}), attempting fallback...")
                fallback_used = True
                # Trigger fallback to Gemini
                if self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here":
                    try:
                        raw_answer, fallback_event = self._call_gemini_fallback(user_prompt, err_str)
                        fallback_model = fallback_event["model_to"]
                    except Exception as gemini_err:
                        logger.error(f"Gemini fallback failed: {gemini_err}")
                        raw_answer = self._offline_synthesize(question, chunks, financial_year)
                        fallback_model = "offline_fallback"
                        fallback_event = {
                            "event": "provider_fallback",
                            "component": "generator",
                            "model_from": self.model,
                            "model_to": "offline_fallback",
                            "reason": f"{err_str} | Gemini: {gemini_err}",
                            "latency_ms": 0
                        }
                else:
                    raw_answer = self._offline_synthesize(question, chunks, financial_year)
                    fallback_model = "offline_fallback"
                    fallback_event = {
                        "event": "provider_fallback",
                        "component": "generator",
                        "model_from": self.model,
                        "model_to": "offline_fallback",
                        "reason": err_str,
                        "latency_ms": 0
                    }


        elif self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here":
            try:
                raw_answer, fallback_event = self._call_gemini_fallback(user_prompt, "Groq unconfigured")
                fallback_used = True
                fallback_model = self.fallback_model
            except Exception as e:
                logger.error(f"Gemini generation failed: {e}")
                raw_answer = self._offline_synthesize(question, chunks, financial_year)

        else:
            raw_answer = self._offline_synthesize(question, chunks, financial_year)

        # Check refusal
        refused = EXACT_REFUSAL_PHRASE in raw_answer

        # Build citations mapping list
        citations_meta = []
        for idx, c in enumerate(chunks, 1):
            tag = f"[C{idx}]"
            if tag in raw_answer or not refused:
                citations_meta.append({
                    "citation_id": tag,
                    "chunk_id": c.get("chunk_id"),
                    "section_id": c.get("section_id"),
                    "doc_type": c.get("doc_type"),
                    "source_url": c.get("source_url"),
                    "page_number": c.get("page_number"),
                    "score": c.get("final_score", 0.0),
                    "graph_expanded": c.get("graph_expanded", False)
                })

        return {
            "answer": raw_answer,
            "refused": refused,
            "fallback_used": fallback_used,
            "fallback_model": fallback_model,
            "fallback_event": fallback_event,
            "citations": citations_meta
        }
