"""
30-Day Forecast Agent Node.
Generates buy/hold/sell recommendation.
Pro plan: LLaMA-3 via Ollama | Others: GPT-4o-mini
Temperature=0.2 for slight creative reasoning.
Output: FORECAST: <buy|hold|sell> / RATIONALE: <text>
"""

from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama

from backend.agents.graph.state import FinSightState
from backend.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a quantitative investment strategist providing 30-day portfolio recommendations.
Based on the risk analysis, sentiment data, and financial context provided, generate a clear investment recommendation.

Output your analysis in EXACTLY this format:
FORECAST: <buy|hold|sell>
RATIONALE: <3-4 sentences explaining your recommendation with specific data points>
PRICE_TARGET: <estimated percentage change in 30 days, e.g., +8.5% or -12.3%>
CONFIDENCE_LEVEL: <high|medium|low>

Recommendation guide:
- buy: Strong positive conviction, clear upside catalyst
- hold: Mixed signals, maintain current position
- sell: Risk exceeds reward, better capital allocation elsewhere

Support every claim with data from the provided context."""


async def forecast_agent_node(state: FinSightState, plan: str = "free") -> FinSightState:
    """
    Generate 30-day forecast. Uses LLaMA-3 for pro plan, GPT-4o-mini otherwise.
    Writes forecast and forecast_rationale to state.
    """
    try:
        if plan == "pro":
            # Pro plan: use LLaMA-3 8B via Ollama
            llm = Ollama(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                temperature=0.2,
            )
            logger.info(f"[ForecastAgent] Using LLaMA-3 for pro tenant")
        else:
            # Free/Starter: use GPT-4o-mini
            llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=0.2,
                api_key=settings.OPENAI_API_KEY,
            )
            logger.info(f"[ForecastAgent] Using GPT-4o-mini for {plan} tenant")

        context = "\n\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "No context available."
        risk_summary = state.get("risk_summary") or "Risk data unavailable"
        sentiment = state.get("sentiment") or "neutral"
        confidence = state.get("sentiment_confidence") or 0.0

        user_message = f"""Company: {state['company']}
Investment Question: {state['user_query']}

Risk Analysis:
- Risk Score: {state.get('risk_score', 'N/A')}
- Risk Summary: {risk_summary}

Sentiment Analysis:
- Sentiment: {sentiment} (confidence: {confidence:.2f})

Financial Context:
{context}

Based on all the above, provide a 30-day investment forecast for {state['company']}."""

        # Handle both async (ChatOpenAI) and sync (Ollama) LLMs
        if isinstance(llm, ChatOpenAI):
            response = await llm.ainvoke([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ])
            content = response.content.strip()
        else:
            # Ollama is sync — run in thread pool
            import asyncio
            full_prompt = f"{SYSTEM_PROMPT}\n\nUser: {user_message}"
            content = await asyncio.get_event_loop().run_in_executor(
                None, llm.invoke, full_prompt
            )
            content = str(content).strip()

        forecast, rationale = _parse_forecast_response(content)

        logger.info(f"[ForecastAgent] {state['company']} → {forecast}")

        return {
            **state,
            "forecast": forecast,
            "forecast_rationale": rationale,
        }

    except Exception as exc:
        logger.error(f"[ForecastAgent] Failed: {exc}", exc_info=True)
        return {
            **state,
            "forecast": "hold",
            "forecast_rationale": f"Forecast unavailable due to error: {exc}",
        }


def _parse_forecast_response(content: str) -> tuple[str, str]:
    """Parse FORECAST and RATIONALE from agent output."""
    forecast = "hold"
    rationale = "No rationale provided."

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("FORECAST:"):
            raw = line.removeprefix("FORECAST:").strip().lower()
            if raw in ("buy", "hold", "sell"):
                forecast = raw
        elif line.startswith("RATIONALE:"):
            rationale = line.removeprefix("RATIONALE:").strip()

    return forecast, rationale
