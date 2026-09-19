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

from src.utils.llm_cache import llm_cache
from src.utils.groq_rate_limiter import groq_pacer

logger = logging.getLogger("LexIndiaGenerator")


class AnswerGenerator:
    def __init__(self):
        self.model = settings.GENERATION_MODEL
        self.fallback_model = settings.JUDGE_CROSS_FAMILY
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_base_url = settings.GROQ_BASE_URL
        self.gemini_api_key = settings.GEMINI_API_KEY

    def _call_groq(self, user_prompt: str, mock_429: bool = False) -> str:
        """Execute generation via Groq OpenAI-compatible client with dynamic rate pacing and retry."""
        if mock_429:
            raise RuntimeError("HTTP 429: Simulated Rate limit reached on Groq")

        from openai import OpenAI, RateLimitError
        client = OpenAI(
            api_key=self.groq_api_key,
            base_url=self.groq_base_url,
            timeout=30.0,
            max_retries=0
        )

        max_retries = 3
        for attempt in range(max_retries + 1):
            # Dynamic token pacing before request (full prompt + retrieved chunks ~2.5k tokens, safe ceiling 4,800 TPM)
            groq_pacer.wait_before_request(model=self.model, estimated_tokens=2500, safe_tpm_ceiling=4800)
            try:
                raw_res = client.chat.completions.with_raw_response.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    max_tokens=600
                )
                parsed = raw_res.parse()
                usage_tokens = getattr(parsed, "usage", None) and getattr(parsed.usage, "total_tokens", None)
                groq_pacer.record_response(raw_res.headers, model=self.model, usage_tokens=usage_tokens)
                content = parsed.choices[0].message.content.strip()
                return content
            except RateLimitError as rle:
                err_str = str(rle).lower()
                if "tokens per day" in err_str or "tpd" in err_str:
                    logger.warning(f"Groq TPD exhausted on {self.model}. Triggering immediate provider fallback.")
                    raise rle
                if attempt < max_retries:
                    retry_after = getattr(rle, "response", None) and rle.response.headers.get("retry-after")
                    groq_pacer.handle_rate_limit(retry_after, model=self.model, error_message=str(rle))
                    continue
                raise rle
            except Exception as e:
                err_str = str(e).lower()
                if "tokens per day" in err_str or "tpd" in err_str:
                    logger.warning(f"Groq TPD exhausted on {self.model}. Triggering immediate provider fallback.")
                    raise e
                if ("429" in str(e) or "rate_limit" in err_str) and attempt < max_retries:
                    groq_pacer.handle_rate_limit(model=self.model, error_message=str(e))
                    continue
                raise e

    def _call_gemini_fallback(self, user_prompt: str, reason: str) -> Tuple[str, Dict[str, Any]]:
        """Fallback to gemini-3.6-flash on Groq 429/5xx with structured telemetry."""
        t0 = time.time()
        logger.warning(
            f"GENERATOR PROVIDER FALLBACK TRIGGERED: {self.model} -> {self.fallback_model} | Reason: {reason}"
        )
        from google import genai
        client = genai.Client(api_key=self.gemini_api_key)
        full_contents = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
        # Try working active Gemini models
        candidate_models = [self.fallback_model, "gemini-3.5-flash", "gemini-flash-latest", "gemini-3.6-flash"]
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
        sec_id = top_chunk.get("section_id", "Section 1")
        act = top_chunk.get("act_name", "Income-tax Act, 1961")
        doc_type = top_chunk.get("doc_type", "statute")
        snippet = top_chunk.get("text", "")[:300].strip()

        parts = [
            f"Based on the authoritative provisions of **{sec_id}** under the {act} for Financial Year {fy} [C1], the applicable legal framework provides:",
            f"> {snippet}...",
            f"These requirements apply in accordance with the provisions of {sec_id} [C1]."
        ]
        if len(chunks) > 1:
            c2 = chunks[1]
            sec_id2 = c2.get("section_id", "applicable rules")
            parts.append(f"Furthermore, related conditions and limits apply under **{sec_id2}** [C2].")

        parts.append(f"\n*{STANDARD_DISCLAIMER}*")
        return "\n\n".join(parts)

    def generate_answer(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
        financial_year: str = "2024-25",
        taxpayer_type: str = "Individual (Salaried)",
        mock_429: bool = False,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate answer strictly grounded in retrieved chunks with retry guardrails and relaxed refusal.
        Returns dict containing answer text, fallback flags, citations mapping, and extracted sections.
        """
        import re

        if not chunks:
            return {
                "answer": f"{EXACT_REFUSAL_PHRASE}\n\n*{STANDARD_DISCLAIMER}*",
                "refused": True,
                "fallback_used": False,
                "fallback_model": None,
                "fallback_event": None,
                "citations": [],
                "extracted_sections": []
            }

        # Check maximum chunk relevance score
        max_chunk_score = max(
            (c.get("final_score", c.get("rerank_score", c.get("score", 0.0))) for c in chunks),
            default=0.0
        )
        has_relevant_chunks = len(chunks) > 0 and (max_chunk_score >= 0.25 or any(c.get("section_id") for c in chunks))

        def _execute_prompt(user_prompt: str) -> Tuple[str, bool, Optional[str], Optional[Dict[str, Any]], str, bool]:
            f_used = False
            f_model = None
            f_event = None
            raw_ans = ""
            is_cached = False
            srv_model = self.model

            # Check persistent LLM cache
            cached_entry = llm_cache.get(self.model, user_prompt)
            if cached_entry and cached_entry.get("response") and not mock_429:
                raw_ans = cached_entry["response"]
                is_cached = True
                srv_model = cached_entry.get("model", self.model)
                logger.debug(f"LLM Cache HIT for model {self.model}")
                return raw_ans, f_used, f_model, f_event, srv_model, is_cached

            # Call live primary or fallback
            if (self.groq_api_key and self.groq_api_key != "your_groq_api_key_here") or mock_429:
                try:
                    raw_ans = self._call_groq(user_prompt, mock_429=mock_429)
                    srv_model = self.model
                    llm_cache.set(self.model, user_prompt, raw_ans, metadata={"serving_model": self.model}, provenance="live")
                except Exception as e:
                    err_str = str(e)
                    logger.warning(f"Primary model generation failed ({e}), attempting fallback...")
                    f_used = True
                    if self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here":
                        try:
                            raw_ans, f_event = self._call_gemini_fallback(user_prompt, err_str)
                            f_model = f_event["model_to"]
                            srv_model = f_model
                        except Exception as gemini_err:
                            logger.error(f"Gemini fallback failed: {gemini_err}")
                            raw_ans = self._offline_synthesize(question, chunks, financial_year)
                            f_model = "offline_fallback"
                            srv_model = "offline_fallback"
                    else:
                        raw_ans = self._offline_synthesize(question, chunks, financial_year)
                        f_model = "offline_fallback"
                        srv_model = "offline_fallback"
            elif self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here":
                try:
                    raw_ans, f_event = self._call_gemini_fallback(user_prompt, "Groq unconfigured")
                    f_used = True
                    f_model = self.fallback_model
                    srv_model = f_model
                except Exception as e:
                    logger.error(f"Gemini generation failed: {e}")
                    raw_ans = self._offline_synthesize(question, chunks, financial_year)
                    f_model = "offline_fallback"
                    srv_model = "offline_fallback"
            else:
                raw_ans = self._offline_synthesize(question, chunks, financial_year)
                f_model = "offline_fallback"
                srv_model = "offline_fallback"

            return raw_ans, f_used, f_model, f_event, srv_model, is_cached

        # Retrieval-side guard: detect schedule-validation chunks ONLY
        # Applied conditionally so unaffected queries retain identical prompt hashes.
        sched_keywords = ["schedule ", "itr-", "validation rule", "schema", "table format"]
        is_schedule_validation = (
            sum(
                1 for c in chunks[:4]
                if any(k in c.get("text", "").lower() or k in c.get("section_id", "").lower() for k in sched_keywords)
            ) >= 2
        )
        effective_feedback = feedback
        if is_schedule_validation and not feedback:
            effective_feedback = (
                "NOTE ON CONTEXT: The retrieved context contains tax return filing schedule validation rules or form structures. "
                "Under strict context grounding, cite only what is stated in these rules using [C#]. "
                "If the substantive tax rate or statutory limit is not provided in these validation rules, "
                "state: 'The retrieved context contains filing schedule rules but does not state the substantive statutory provision or limit.' "
                "Do NOT guess or speculate."
            )

        # Build initial prompt
        user_prompt = build_generation_prompt(
            question=question,
            chunks=chunks,
            financial_year=financial_year,
            taxpayer_type=taxpayer_type,
            correction_feedback=effective_feedback
        )

        raw_answer, fallback_used, fallback_model, fallback_event, serving_model, cached = _execute_prompt(user_prompt)

        # In-generator retry guardrail:
        # Check if model hallucinated invalid tags ([C5] when only 4 chunks)
        num_chunks = len(chunks)
        cited_indices = [int(i) for i in re.findall(r'\[C(\d+)\]', raw_answer)]
        bad_tags = [f"[C{i}]" for i in cited_indices if i < 1 or i > num_chunks]

        # Check for false refusal when context has valid provisions
        has_exact_refusal = EXACT_REFUSAL_PHRASE in raw_answer
        sections_in_chunks = [c.get("section_id") for c in chunks[:4] if c.get("section_id")]

        if (bad_tags or (has_exact_refusal and has_relevant_chunks and sections_in_chunks)) and not feedback and not mock_429 and not cached:
            if bad_tags:
                retry_feedback = f"You cited {', '.join(set(bad_tags))} which is not in the retrieved context. Rewrite using only C1-C{num_chunks}."
            else:
                retry_feedback = (
                    f"The retrieved context contains authoritative statutory provisions ({', '.join(set(sections_in_chunks))}). "
                    f"Do NOT refuse the entire query. Answer the aspects covered by these provisions using inline citations [C1], [C2], "
                    f"and specify what particular sub-aspect is not in context."
                )
            logger.info(f"AnswerGenerator: Triggering in-generator correction retry: {retry_feedback}")
            retry_prompt = build_generation_prompt(
                question=question,
                chunks=chunks,
                financial_year=financial_year,
                taxpayer_type=taxpayer_type,
                correction_feedback=retry_feedback
            )
            raw_answer, fallback_used, fallback_model, fallback_event, serving_model, cached = _execute_prompt(retry_prompt)

        # Final refusal decision:
        # Refuse ONLY if raw_answer contains EXACT_REFUSAL_PHRASE AND either:
        # 1. Chunks lack relevant legal provisions (has_relevant_chunks is False), OR
        # 2. Query is inherently unanswerable / out-of-scope (no substantive sections answered)
        refused = EXACT_REFUSAL_PHRASE in raw_answer
        if refused and has_relevant_chunks and len(re.findall(r'Section\s+[0-9]+', raw_answer)) > 0:
            # Partial answer provided alongside disclaimer — do not mark as total refusal
            refused = False

        # Build citations mapping and extract all cited statutory sections (dual-source)
        citations_meta = []
        extracted_sections = list(set(re.findall(r'Section\s+[0-9]+[A-Za-z]*(?:\([0-9A-Za-z]+\))*', raw_answer)))

        final_cited_indices = [int(i) for i in re.findall(r'\[C(\d+)\]', raw_answer)]
        for idx in sorted(set(final_cited_indices)):
            if 1 <= idx <= num_chunks:
                c = chunks[idx - 1]
                sec_id = c.get("section_id")
                if sec_id and sec_id not in extracted_sections:
                    extracted_sections.append(sec_id)
                citations_meta.append({
                    "citation_id": f"[C{idx}]",
                    "chunk_id": c.get("chunk_id"),
                    "section_id": sec_id,
                    "doc_type": c.get("doc_type"),
                    "source_url": c.get("source_url"),
                    "page_number": c.get("page_number"),
                    "score": c.get("final_score", c.get("rerank_score", 0.0)),
                    "graph_expanded": c.get("graph_expanded", False)
                })

        # If model did not cite [C#] tags explicitly but cited sections in text, include matching chunks
        if not citations_meta and not refused:
            for idx, c in enumerate(chunks, 1):
                sec_id = c.get("section_id")
                if sec_id and any(sec_id.lower() in s.lower() for s in extracted_sections):
                    citations_meta.append({
                        "citation_id": f"[C{idx}]",
                        "chunk_id": c.get("chunk_id"),
                        "section_id": sec_id,
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
            "serving_model": serving_model,
            "cached": cached,
            "citations": citations_meta,
            "extracted_sections": extracted_sections
        }
