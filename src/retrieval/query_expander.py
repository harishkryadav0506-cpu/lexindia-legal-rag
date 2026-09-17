"""
src/retrieval/query_expander.py — Query Expansion with Provider Fallback.

Strictly adheres to SPEC.md section #6 and section #8:
- Uses EXPANSION_MODEL (default qwen/qwen3.8-27b via Groq, temp 0.3).
- Produces exactly 3 variants:
  (a) formal legal phrasing with probable section references
  (b) layman English
  (c) English legal reformulation if input is Hinglish/colloquial, else keyword-boosted variant
- Provider fallback: if Groq returns 429/5xx after retries, automatically route
  to gemini-2.5-flash and log a structured fallback event.
- Robust rule-based legal expansion fallback if offline or keys unconfigured.
"""

import json
import logging
import re
import time
from typing import List, Dict, Any, Optional

from src.config import settings

logger = logging.getLogger("LexIndiaQueryExpander")

SYSTEM_PROMPT = """You are an expert Indian Income Tax legal research assistant.
Given a user's tax query, produce EXACTLY three distinct search query variants in valid JSON array format:
Variant 1 (Formal Legal): Formal legal phrasing specifying probable Sections, Rules, or Act names (e.g. Income-tax Act, 1961, Section 80C, Section 10(13A), Rule 2A).
Variant 2 (Layman English): Simplified, plain English query capturing practical user intent without statutory jargon.
Variant 3 (Reformulation): If input is Hinglish or colloquial, translate to clear English legal phrasing; otherwise, generate a high-precision keyword-boosted variant.

Output MUST be a valid JSON array of exactly 3 strings:
["variant 1", "variant 2", "variant 3"]
Do NOT include markdown fences, preambles, or explanations. Just the raw JSON array."""


class QueryExpander:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.expansion_model = settings.EXPANSION_MODEL
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_base_url = settings.GROQ_BASE_URL
        self.gemini_api_key = settings.GEMINI_API_KEY

    def _rule_based_fallback(self, query: str) -> List[str]:
        """Deterministic offline rule-based fallback generating 3 variants."""
        q_clean = query.strip()
        q_lower = q_clean.lower()

        # Detect topic
        probable_section = ""
        if "80c" in q_lower or "lic" in q_lower or "ppf" in q_lower or "elss" in q_lower:
            probable_section = "Section 80C deduction limit eligible investments"
        elif "hra" in q_lower or "rent" in q_lower or "kiraya" in q_lower or "makan" in q_lower:
            probable_section = "Section 10(13A) Rule 2A house rent allowance exemption calculation"
        elif "home loan" in q_lower or "interest on loan" in q_lower or "house property" in q_lower:
            probable_section = "Section 24(b) interest on borrowed capital house property deduction"
        elif "audit" in q_lower or "turnover" in q_lower or "44ab" in q_lower:
            probable_section = "Section 44AB tax audit accounts turnover limits"
        elif "slab" in q_lower or "regime" in q_lower or "old vs new" in q_lower or "tax rate" in q_lower:
            probable_section = "Section 115BAC new tax regime vs old tax regime slab rates rebate 87A"
        elif "tds" in q_lower:
            probable_section = "Section 192 Section 194 TDS deduction rate threshold"
        else:
            probable_section = f"Income-tax Act 1961 statutory provisions {q_clean}"

        # Variant 1: Formal legal phrasing with probable section
        var_a = f"{probable_section} provisions Income Tax Act 1961"

        # Variant 2: Layman English
        var_b = f"how to calculate or claim {q_clean} for income tax return filing"

        # Variant 3: Hinglish translation / keyword boost
        # Detect Hinglish terms
        hinglish_terms = ["kya", "main", "apne", "ka", "sakta", "hu", "hai", "chahiye", "kitna", "kisko"]
        is_hinglish = any(re.search(rf"\b{term}\b", q_lower) for term in hinglish_terms)
        if is_hinglish:
            # Strip Hinglish stop words and reformulate in English legal terms
            words = [w for w in re.split(r'\W+', q_lower) if w and w not in hinglish_terms]
            core_words = " ".join(words)
            var_c = f"eligibility and rules for {core_words} under Indian tax law"
        else:
            var_c = f"{q_clean} exemption conditions limits guidelines circular notification"

        return [var_a, var_b, var_c]

    def _call_groq(self, query: str) -> List[str]:
        """Invoke primary expansion model via Groq OpenAI-compatible client."""
        from openai import OpenAI
        client = OpenAI(
            api_key=self.groq_api_key,
            base_url=self.groq_base_url,
            timeout=15.0
        )
        response = client.chat.completions.create(
            model=self.expansion_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Query: {query}"}
            ],
            temperature=0.3,
            max_tokens=300
        )
        raw_text = response.choices[0].message.content.strip()
        return self._parse_variants(raw_text)

    def _call_gemini_fallback(self, query: str, reason: str) -> List[str]:
        """Fallback to gemini-2.5-flash and log structured fallback event."""
        t0 = time.time()
        logger.warning(
            f"FALLBACK TRIGGERED: {self.expansion_model} -> gemini-2.5-flash | Reason: {reason}"
        )
        from google import genai
        client = genai.Client(api_key=self.gemini_api_key)
        prompt = f"{SYSTEM_PROMPT}\n\nUser Query: {query}"
        response = client.models.generate_content(
            model=settings.JUDGE_PRIMARY,
            contents=prompt,
        )
        latency_ms = int((time.time() - t0) * 1000)
        fallback_event = {
            "event": "provider_fallback",
            "component": "query_expander",
            "model_from": self.expansion_model,
            "model_to": settings.JUDGE_PRIMARY,
            "reason": reason,
            "latency_ms": latency_ms
        }
        logger.info(f"STRUCTURED_FALLBACK_EVENT: {json.dumps(fallback_event)}")
        raw_text = response.text.strip()
        return self._parse_variants(raw_text)

    def _parse_variants(self, raw_text: str) -> List[str]:
        """Parse 3 query variants from model output."""
        # Strip code fences if present
        clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
        try:
            parsed = json.loads(clean_json)
            if isinstance(parsed, list) and len(parsed) >= 3:
                return [str(v).strip() for v in parsed[:3]]
        except Exception:
            pass

        # Fallback to line-by-line parsing
        lines = [line.strip().lstrip("0123456789.-*•\"' ") for line in raw_text.split("\n") if line.strip()]
        if len(lines) >= 3:
            return lines[:3]

        raise ValueError(f"Could not parse 3 variants from model output: {raw_text}")

    def expand(self, query: str) -> List[str]:
        """Expand user query into exactly 3 variants with automatic provider fallback."""
        query = query.strip()
        if not query:
            return ["", "", ""]

        # If Groq API key is present, attempt primary model with retries
        if self.groq_api_key and self.groq_api_key != "your_groq_api_key_here":
            max_retries = 2
            last_err = None
            for attempt in range(max_retries):
                try:
                    return self._call_groq(query)
                except Exception as e:
                    last_err = e
                    err_str = str(e).lower()
                    logger.warning(f"Groq expansion attempt {attempt+1} failed: {e}")
                    # If rate limited (429) or server error (5xx)
                    if "429" in err_str or "500" in err_str or "503" in err_str or attempt == max_retries - 1:
                        break
                    time.sleep(1.0 * (attempt + 1))

            # Attempt Gemini fallback if key available
            if self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here":
                try:
                    return self._call_gemini_fallback(query, str(last_err))
                except Exception as gemini_err:
                    logger.error(f"Gemini fallback also failed: {gemini_err}")

        # If Gemini key is available without Groq key
        elif self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here":
            try:
                return self._call_gemini_fallback(query, "Groq API key not configured")
            except Exception as gemini_err:
                logger.error(f"Gemini expansion failed: {gemini_err}")

        # Deterministic offline legal expansion fallback
        logger.info(f"Using rule-based legal expansion for: '{query}'")
        return self._rule_based_fallback(query)
