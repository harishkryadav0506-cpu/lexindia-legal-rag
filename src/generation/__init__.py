"""
LexIndia Generation & Safety Package.
Provides prompt templates, answer generator with provider fallback,
and neural faithfulness verification gate.
"""

from src.generation.prompts import (
    SYSTEM_PROMPT,
    EXACT_REFUSAL_PHRASE,
    STANDARD_DISCLAIMER,
    build_generation_prompt,
)
from src.generation.generator import AnswerGenerator
from src.generation.faithfulness_gate import FaithfulnessGate

__all__ = [
    "SYSTEM_PROMPT",
    "EXACT_REFUSAL_PHRASE",
    "STANDARD_DISCLAIMER",
    "build_generation_prompt",
    "AnswerGenerator",
    "FaithfulnessGate",
]
