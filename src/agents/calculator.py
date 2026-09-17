"""
src/agents/calculator.py — Calculator Agent for slab-wise Old vs New Regime computation.

Strictly adheres to SPEC.md section #7:
- Uses calc_tax_old_vs_new tool.
- Answer includes computation table + citations.
- Populates calculation_result, draft_answer, and appends to agent_trace.
"""

import re
import time
import logging
from typing import Dict, Any

from src.agents.state import LexIndiaState
from src.agents.tools import calc_tax_old_vs_new, retrieve_sections

logger = logging.getLogger("LexIndiaCalculator")


class CalculatorAgent:
    def __init__(self):
        pass

    def _extract_income(self, question: str) -> float:
        """Parse income figures from query (e.g. '15 lakh', '1500000', '12.5L')."""
        q_lower = question.lower()

        # Check for 'X lakh' or 'X lac'
        lakh_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|lac|l)\b', q_lower)
        if lakh_match:
            val = float(lakh_match.group(1))
            return val * 100000.0

        # Check for direct number like '15,00,000' or '1500000'
        num_match = re.search(r'\b([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]+)?)\b', question)
        if num_match:
            clean_str = num_match.group(1).replace(",", "")
            val = float(clean_str)
            if val > 50000:
                return val

        # Default standard income benchmark: Rs 15,00,000 (15 Lakhs)
        return 1500000.0

    def run(self, state: LexIndiaState) -> LexIndiaState:
        """Execute tax computation and construct cited comparison answer."""
        t0 = time.time()
        question = state["question"]
        fy = state.get("financial_year", "2025-26")
        if "2025-26" in question:
            fy = "2025-26"
        elif "2024-25" in question:
            fy = "2024-25"

        gross_income = self._extract_income(question)

        # Standard sample deductions for individual salaried comparison
        sample_deductions = {
            "80C": 150000.0,
            "80D": 25000.0,
            "24(b)": 0.0
        }

        calc_result = calc_tax_old_vs_new(
            fy=fy,
            gross_income=gross_income,
            deductions=sample_deductions,
            is_salaried=True
        )

        # Retrieve statutory chunks for Section 115BAC & Section 87A for provenance
        sec_chunks = retrieve_sections("Section 115BAC tax slab rates and Section 87A rebate", financial_year=fy)

        draft = (
            f"## Tax Computation Analysis for FY {fy}\n\n"
            f"For an annual taxable salary income of **Rs {gross_income:,.0f}**, "
            f"the comparative analysis between the **Old Tax Regime** and the **New Tax Regime (Section 115BAC)** "
            f"is summarized below [C1]:\n\n"
            f"{calc_result['comparison_table_md']}\n\n"
            f"### Statutory Provisions & Deductions Considered:\n"
            f"- **Section 115BAC (New Regime)**: Provides concessional slab rates with higher standard deduction [C1].\n"
            f"- **Section 87A Rebate**: Available up to Rs 25,000 for taxable income up to Rs 7,00,000 under New Regime [C2].\n"
            f"- **Old Regime Deductions**: Section 80C (Rs 1,50,000) and Section 80D (Rs 25,000) apply only under the Old Regime [C3].\n\n"
            f"*LexIndia provides legal information, not professional tax advice.*"
        )

        latency_ms = int((time.time() - t0) * 1000)

        trace_entry = {
            "agent": "CalculatorAgent",
            "action": f"Executed tax computation for Rs {gross_income:,.0f} ({fy})",
            "latency_ms": latency_ms,
            "inputs_summary": f"Gross Income: Rs {gross_income:,.0f}, FY: {fy}",
            "outputs_summary": f"Recommended: {calc_result['recommended_regime']}, Net Savings: Rs {abs(calc_result['tax_difference']):,.0f}"
        }

        new_state = dict(state)
        new_state["calculation_result"] = calc_result
        new_state["draft_answer"] = draft
        new_state["final_answer"] = draft
        new_state["retrieved_chunks"] = sec_chunks[:4] if sec_chunks else []
        new_state.setdefault("agent_trace", []).append(trace_entry)

        return new_state
