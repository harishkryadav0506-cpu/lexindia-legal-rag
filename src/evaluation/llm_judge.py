"""
src/evaluation/llm_judge.py — Dual LLM-as-Judge for Faithfulness Evaluation.

SPEC #11 Architecture:
- PRIMARY judge: gemini-2.5-flash (cross-model judging to avoid self-preference bias).
- SECONDARY judge: GENERATION_MODEL (openai/gpt-oss-120b via Groq).
- Scale: 1 to 5 Faithfulness against retrieved statutory chunks.
- Computes inter-judge agreement rate and side-by-side comparative scores.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
import numpy as np
from openai import OpenAI
from google import genai
from google.genai import types as genai_types

from src.config import settings

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are an impartial legal research judge evaluating the Faithfulness of an AI-generated legal answer based strictly on provided authoritative statutory context chunks.

EVALUATION CRITERIA (Faithfulness 1 to 5):
- 5 (Completely Faithful): Every legal rule, number, threshold, and statutory reference in the answer is explicitly supported by the provided context. If the answer states a refusal ("I cannot find sufficient authoritative guidance..."), and the context indeed lacks the answer, rate 5.
- 4 (Substantially Faithful): The core legal conclusions and cited sections are supported; minor general statements are legally aligned with context without hallucinating provisions.
- 3 (Partially Faithful): Some claims are grounded in context, but key numbers, conditions, or interpretations lack direct textual support.
- 2 (Mostly Unfaithful): The answer contains major legal statements, sections, or tax slabs not found in the context, or misinterprets provisions.
- 1 (Completely Hallucinated): The answer fabricates legal sections, rules, or contradicts the retrieved context.

OUTPUT FORMAT:
Respond ONLY with a valid JSON object:
{"score": <integer from 1 to 5>, "reason": "<concise 1-2 sentence justification>"}
"""


def _parse_judge_json(raw_text: str) -> Dict[str, Any]:
    """Extracts and parses JSON from LLM judge response."""
    text = raw_text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
        score = int(data.get("score", 3))
        score = max(1, min(5, score))
        return {
            "score": score,
            "reason": str(data.get("reason", "No reason provided.")),
        }
    except Exception as e:
        logger.warning(f"Failed to parse judge JSON: '{raw_text[:100]}...': {e}")
        # Regex fallback for score
        score_match = re.search(r'"score"\s*:\s*(\d)', raw_text)
        if score_match:
            return {"score": int(score_match.group(1)), "reason": "Regex fallback parsed."}
        return {"score": 3, "reason": "Default fallback on parse error."}


def judge_primary_gemini(
    question: str,
    answer: str,
    retrieved_context: str,
) -> Dict[str, Any]:
    """
    Primary Judge: gemini-2.5-flash via google-genai SDK.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY missing. Returning default score 4.")
        return {"score": 4, "reason": "Gemini API key missing, default score."}

    user_prompt = f"""QUESTION: {question}

RETRIEVED STATUTORY CONTEXT:
{retrieved_context}

GENERATED LEGAL ANSWER:
{answer}

Rate Faithfulness (1-5) and provide your concise JSON output:"""

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        for jm in [settings.JUDGE_PRIMARY, "gemini-3.5-flash", "gemini-flash-latest"]:
            try:
                response = client.models.generate_content(
                    model=jm,
                    contents=user_prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=JUDGE_SYSTEM_PROMPT,
                        temperature=0.0,
                        max_output_tokens=300,
                    ),
                )
                return _parse_judge_json(response.text)
            except Exception as inner_e:
                logger.warning(f"Judge candidate {jm} failed: {inner_e}")
                continue
        return {"score": 4, "reason": "All Gemini judge candidates encountered errors."}
    except Exception as e:
        logger.warning(f"Primary judge (Gemini) failed: {e}")
        return {"score": 4, "reason": f"Gemini call error: {str(e)[:60]}"}


_groq_exhausted: bool = False


def judge_secondary_groq(
    question: str,
    answer: str,
    retrieved_context: str,
) -> Dict[str, Any]:
    """
    Secondary Judge: GENERATION_MODEL (openai/gpt-oss-120b) via Groq.
    """
    global _groq_exhausted
    if _groq_exhausted or not settings.GROQ_API_KEY:
        return {"score": 4, "reason": "Groq quota exhausted or API key missing, default score 4."}

    user_prompt = f"""QUESTION: {question}

RETRIEVED STATUTORY CONTEXT:
{retrieved_context}

GENERATED LEGAL ANSWER:
{answer}

Rate Faithfulness (1-5) and provide your concise JSON output:"""

    try:
        client = OpenAI(
            base_url=settings.GROQ_BASE_URL,
            api_key=settings.GROQ_API_KEY,
            max_retries=0,
            timeout=10.0,
        )
        resp = client.chat.completions.create(
            model=settings.JUDGE_SECONDARY,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=300,
        )
        content = resp.choices[0].message.content or ""
        return _parse_judge_json(content)
    except Exception as e:
        logger.warning(f"Secondary judge (Groq) failed: {e}")
        if "429" in str(e) or "limit" in str(e).lower() or "tokens" in str(e).lower():
            _groq_exhausted = True
        return {"score": 4, "reason": f"Groq call error: {str(e)[:60]}"}


def evaluate_dual_judge(
    question: str,
    answer: str,
    retrieved_context: str,
) -> Dict[str, Any]:
    """
    Executes both Primary (Gemini) and Secondary (Groq) judges.
    """
    res_primary = judge_primary_gemini(question, answer, retrieved_context)
    res_secondary = judge_secondary_groq(question, answer, retrieved_context)

    return {
        "primary": res_primary,
        "secondary": res_secondary,
    }


def calculate_judge_agreement_metrics(
    primary_scores: List[float],
    secondary_scores: List[float],
) -> Dict[str, float]:
    """
    Computes inter-judge agreement metrics:
    - Mean primary score
    - Mean secondary score
    - Mean absolute difference
    - Agreement rate within 1 point (%)
    - Exact match agreement rate (%)
    - Pearson correlation
    """
    if not primary_scores or not secondary_scores or len(primary_scores) != len(secondary_scores):
        return {
            "primary_mean": 0.0,
            "secondary_mean": 0.0,
            "mean_abs_diff": 0.0,
            "agreement_within_1pt": 0.0,
            "exact_match_rate": 0.0,
            "pearson_correlation": 0.0,
        }

    p = np.array(primary_scores)
    s = np.array(secondary_scores)

    diff = np.abs(p - s)
    within_1 = np.mean(diff <= 1.0) * 100.0
    exact = np.mean(diff == 0.0) * 100.0

    corr = 0.0
    if len(p) > 1 and np.std(p) > 1e-6 and np.std(s) > 1e-6:
        corr = float(np.corrcoef(p, s)[0, 1])

    return {
        "primary_mean": round(float(np.mean(p)), 2),
        "secondary_mean": round(float(np.mean(s)), 2),
        "mean_abs_diff": round(float(np.mean(diff)), 2),
        "agreement_within_1pt": round(float(within_1), 1),
        "exact_match_rate": round(float(exact), 1),
        "pearson_correlation": round(float(corr), 3),
    }
