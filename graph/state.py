from typing import TypedDict, Optional

class FinSightState(TypedDict):
    # Input
    user_query: str
    company: str                    # e.g. "AAPL"

    # RAG context (filled by orchestrator before routing)
    retrieved_docs: list[str]

    # Agent outputs (each agent fills its own field)
    risk_score: Optional[float]     # 0.0 to 1.0
    risk_summary: Optional[str]
    sentiment: Optional[str]        # "bullish" | "bearish" | "neutral"
    sentiment_confidence: Optional[float]
    forecast: Optional[str]
    forecast_rationale: Optional[str]

    # Final output
    decision_report: Optional[str]
    error: Optional[str]