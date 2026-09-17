"""
src/generation/prompts.py — System prompts, prompt builders, and safety disclaimers for LexIndia.

Strictly adheres to SPEC.md section #8:
- System prompt defines Indian tax legal research assistant.
- Mandatory rule: Cite every factual claim using [C1], [C2], etc. mapped to retrieved chunks.
- Mandatory refusal rule: When context is insufficient, refuse with exact phrase:
  "I cannot find sufficient authoritative guidance for this query."
- Context includes financial year and taxpayer profile.
- Appends standard disclaimer: "LexIndia provides legal information, not professional tax advice."
"""

EXACT_REFUSAL_PHRASE = "I cannot find sufficient authoritative guidance for this query."
STANDARD_DISCLAIMER = "LexIndia provides legal information, not professional tax advice."

SYSTEM_PROMPT = f"""You are LexIndia, an authoritative Indian Income Tax legal research assistant.
Your goal is to provide precise, legally sound answers grounded strictly in the provided authoritative legal context (statutes, rules, finance acts, and circulars).

CRITICAL RULES:
1. CITATIONS: Every single statement, provision, condition, and rate you mention MUST be accompanied by an inline citation chip [C1], [C2], etc., directly pointing to the numbered source chunk provided below.
2. REFUSAL: If the provided context does not contain sufficient authoritative guidance to answer the question accurately, or if the question is completely ambiguous/unsupported, you MUST respond with the exact phrase:
   "{EXACT_REFUSAL_PHRASE}"
   Do not guess, extrapolate, or inject outside knowledge.
3. FINANCIAL YEAR: Note the specific Financial Year (FY) requested by the user. If tax laws or slab rates differ between the Old and New Regime (Section 115BAC), explicitly delineate the difference.
4. TONE & STRUCTURE: Maintain a professional, objective legal advisory tone. Format complex provisions using clear markdown bullet points or comparative tables.
5. DISCLAIMER: Always conclude your response with the disclaimer:
   "*{STANDARD_DISCLAIMER}*"
"""


def build_generation_prompt(
    question: str,
    chunks: list,
    financial_year: str = "2024-25",
    taxpayer_type: str = "Individual (Salaried)"
) -> str:
    """Format user question and retrieved chunks into structured prompt."""
    context_blocks = []
    for idx, c in enumerate(chunks, 1):
        chunk_id = c.get("chunk_id", f"c{idx}")
        section_id = c.get("section_id", "Unknown Section")
        doc_type = c.get("doc_type", "statute")
        act_name = c.get("act_name", c.get("doc_id", "Income-tax Act, 1961"))
        page_num = c.get("page_number", 1)
        text = c.get("text", "").strip()

        block = (
            f"[C{idx}] (ID: {chunk_id} | {section_id} | {act_name} | {doc_type.upper()} | Page {page_num}):\n"
            f"{text}"
        )
        context_blocks.append(block)

    joined_context = "\n\n".join(context_blocks)

    user_prompt = f"""CONTEXT:
Financial Year (FY): {financial_year}
Taxpayer Classification: {taxpayer_type}

AUTHORITATIVE LEGAL CHUNKS:
{joined_context}

USER QUESTION:
{question}

Please provide your cited legal analysis below strictly grounded in the numbered chunks above. Remember to cite every claim as [C1], [C2], etc."""
    return user_prompt
