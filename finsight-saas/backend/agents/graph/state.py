"""
FinSightState — the shared TypedDict that flows through the LangGraph pipeline.
All agents read from and write to this state object.
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict


class FinSightState(TypedDict):
    # Input
    user_query: str
    company: str
    namespace: str  # Pinecone namespace = tenant_id

    # RAG outputs
    retrieved_docs: list[str]

    # Risk agent outputs
    risk_score: Optional[float]        # 0.0 – 1.0
    risk_summary: Optional[str]

    # Sentiment agent outputs
    sentiment: Optional[str]           # "bullish" | "bearish" | "neutral"
    sentiment_confidence: Optional[float]  # 0.0 – 1.0

    # Forecast agent outputs
    forecast: Optional[str]            # "buy" | "hold" | "sell"
    forecast_rationale: Optional[str]

    # Report generator output
    decision_report: Optional[str]

    # Error propagation
    error: Optional[str]
