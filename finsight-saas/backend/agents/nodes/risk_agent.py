"""
Risk Analyst Agent Node.
Analyzes financial risk from retrieved context.
Temperature=0, GPT-4o-mini.
Output format: SCORE: <float> / SUMMARY: <text>
"""

from __future__ import annotations

import logging
import re

from langchain_openai import ChatOpenAI

from backend.agents.graph.state import FinSightState
from backend.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior financial risk analyst. 
Your job is to assess the investment risk of a given company based on the provided context.

Output your analysis in EXACTLY this format (no extra text before or after):
SCORE: <number between 0.0 and 1.0, where 1.0 = maximum risk>
SUMMARY: <2-3 sentences explaining key risk factors>

Risk scoring guide:
- 0.0–0.3: Low risk (stable financials, strong moat, good liquidity)
- 0.4–0.6: Medium risk (some volatility, competitive pressures)
- 0.7–1.0: High risk (high debt, regulatory concerns, market disruption)

Be objective, data-driven, and concise."""


async def risk_analyst_node(state: FinSightState) -> FinSightState:
    """Analyze financial risk from retrieved docs. Writes risk_score and risk_summary."""
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    )

    context = "\n\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "No financial documents available."

    user_message = f"""Company: {state['company']}
Question: {state['user_query']}

Retrieved Financial Context:
{context}

Analyze the investment risk for {state['company']} based on the above context."""

    try:
        response = await llm.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ])

        content = response.content.strip()
        risk_score, risk_summary = _parse_risk_response(content)

        logger.info(f"[RiskAgent] {state['company']} → score={risk_score}")

        return {
            **state,
            "risk_score": risk_score,
            "risk_summary": risk_summary,
        }

    except Exception as exc:
        logger.error(f"[RiskAgent] Failed: {exc}", exc_info=True)
        return {
            **state,
            "risk_score": 0.5,
            "risk_summary": f"Risk analysis unavailable: {exc}",
        }


def _parse_risk_response(content: str) -> tuple[float, str]:
    """Parse SCORE and SUMMARY from agent response."""
    score = 0.5
    summary = "Risk analysis could not be parsed."

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("SCORE:"):
            raw = line.removeprefix("SCORE:").strip()
            try:
                parsed = float(re.findall(r"\d+\.?\d*", raw)[0])
                score = max(0.0, min(1.0, parsed))
            except (IndexError, ValueError):
                pass
        elif line.startswith("SUMMARY:"):
            summary = line.removeprefix("SUMMARY:").strip()

    return score, summary
