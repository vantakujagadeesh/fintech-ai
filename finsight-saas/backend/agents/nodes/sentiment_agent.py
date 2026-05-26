"""
Market Sentiment Agent Node.
Determines bullish/bearish/neutral sentiment from news + financials.
Temperature=0, GPT-4o-mini.
Output: SENTIMENT: <bullish|bearish|neutral> / CONFIDENCE: <float>
"""

from __future__ import annotations

import logging
import re

from langchain_openai import ChatOpenAI

from backend.agents.graph.state import FinSightState
from backend.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a market sentiment analyst specializing in equity research.
Analyze the provided financial news and documents to determine market sentiment for the given company.

Output your analysis in EXACTLY this format:
SENTIMENT: <bullish|bearish|neutral>
CONFIDENCE: <number between 0.0 and 1.0>
REASONING: <1-2 sentences explaining the sentiment>

Sentiment definitions:
- bullish: Strong positive momentum, strong earnings, positive catalysts
- bearish: Negative momentum, declining revenues, headwinds
- neutral: Mixed signals, awaiting catalysts, sideways movement

Be precise. Use only the three allowed sentiment values."""


async def sentiment_agent_node(state: FinSightState) -> FinSightState:
    """Analyze market sentiment. Writes sentiment, sentiment_confidence to state."""
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    )

    context = "\n\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "No market data available."

    user_message = f"""Company: {state['company']}
Investment Question: {state['user_query']}

Market & Financial Context:
{context}

Assess the current market sentiment for {state['company']}."""

    try:
        response = await llm.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ])

        content = response.content.strip()
        sentiment, confidence, reasoning = _parse_sentiment_response(content)

        logger.info(f"[SentimentAgent] {state['company']} → {sentiment} ({confidence:.2f})")

        return {
            **state,
            "sentiment": sentiment,
            "sentiment_confidence": confidence,
        }

    except Exception as exc:
        logger.error(f"[SentimentAgent] Failed: {exc}", exc_info=True)
        return {
            **state,
            "sentiment": "neutral",
            "sentiment_confidence": 0.0,
        }


def _parse_sentiment_response(content: str) -> tuple[str, float, str]:
    """Parse SENTIMENT, CONFIDENCE, REASONING from agent output."""
    sentiment = "neutral"
    confidence = 0.5
    reasoning = ""

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("SENTIMENT:"):
            raw = line.removeprefix("SENTIMENT:").strip().lower()
            if raw in ("bullish", "bearish", "neutral"):
                sentiment = raw
        elif line.startswith("CONFIDENCE:"):
            raw = line.removeprefix("CONFIDENCE:").strip()
            try:
                parsed = float(re.findall(r"\d+\.?\d*", raw)[0])
                confidence = max(0.0, min(1.0, parsed))
            except (IndexError, ValueError):
                pass
        elif line.startswith("REASONING:"):
            reasoning = line.removeprefix("REASONING:").strip()

    return sentiment, confidence, reasoning
