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
1. CITATIONS: Every single substantive legal claim, statutory condition, monetary threshold, exemption limit, and section reference MUST be immediately followed by an inline citation chip [C1], [C2], etc., directly pointing to the numbered source chunk provided below.
2. EXPLICIT SECTION NAMING: Always explicitly mention the statutory Section (e.g., Section 80C [C1], Section 10(13A) [C2], Section 24(b) [C3]) alongside its citation chip.
3. GROUNDING & PARTIAL COVERAGE: If the provided context covers only part of the user's question, answer the covered parts thoroughly with citations [C#], and state: "I cannot answer this specific aspect based on the retrieved context" for any uncovered aspects.
4. REFUSAL: ONLY output the exact refusal phrase:
   "{EXACT_REFUSAL_PHRASE}"
   if the entire query is completely out-of-scope (e.g. GST, customs, criminal law) OR if none of the provided chunks contain relevant statutory guidance. DO NOT refuse an answerable question if relevant provisions are present in the context.
5. FINANCIAL YEAR: Note the specific Financial Year (FY) requested by the user. If tax laws or slab rates differ between the Old and New Regime (Section 115BAC), explicitly delineate the difference.
6. TONE & STRUCTURE: Maintain a professional, objective legal advisory tone. Format complex provisions using clear markdown bullet points or comparative tables.
7. DISCLAIMER: Always conclude your response with the disclaimer:
   "*{STANDARD_DISCLAIMER}*"
"""


def build_generation_prompt(
    question: str,
    chunks: list,
    financial_year: str = "2024-25",
    taxpayer_type: str = "Individual (Salaried)",
    correction_feedback: str = None
) -> str:
    """Format user question, retrieved chunks, and optional correction feedback into structured prompt."""
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

    feedback_block = ""
    if correction_feedback:
        feedback_block = f"""
ATTENTION - CORRECTION REQUIRED:
{correction_feedback}
Please revise your answer to fix this issue immediately while remaining strictly grounded in the numbered chunks.
"""

    user_prompt = f"""CONTEXT:
Financial Year (FY): {financial_year}
Taxpayer Classification: {taxpayer_type}

AUTHORITATIVE LEGAL CHUNKS:
{joined_context}
{feedback_block}
USER QUESTION:
{question}

Please provide your cited legal analysis below strictly grounded in the numbered chunks above. Remember:
- Name the statutory section explicitly alongside its citation chip (e.g. Section 80C [C1]).
- If certain sub-aspects are not in the context, state "I cannot answer this specific aspect based on the retrieved context" for those parts rather than refusing the entire question.
- Every single legal claim must be followed immediately by [C1], [C2], etc."""
    return user_prompt

