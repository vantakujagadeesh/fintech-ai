"""
LangGraph StateGraph builder for the FinSight AI agent pipeline.

Execution order:
  1. orchestrator_node  (sequential — RAG retrieval)
  2. risk_analyst_node  ─┐
  3. sentiment_node      ├─ parallel fan-out
  4. forecast_node      ─┘
  5. report_generator_node → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.agents.graph.state import FinSightState
from backend.agents.nodes.orchestrator import orchestrator_node
from backend.agents.nodes.risk_agent import risk_analyst_node
from backend.agents.nodes.sentiment_agent import sentiment_agent_node
from backend.agents.nodes.forecast_agent import forecast_agent_node
from backend.agents.nodes.report_generator import report_generator_node


def build_graph(plan: str = "free") -> StateGraph:
    """
    Compiles the FinSight LangGraph.
    The `plan` parameter is threaded into the forecast node
    (pro plan uses LLaMA-3, others use GPT-4o-mini).
    """
    graph = StateGraph(FinSightState)

    # ── Add nodes ─────────────────────────────────────────────────────────────
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("risk_analyst", risk_analyst_node)
    graph.add_node("sentiment_agent", sentiment_agent_node)

    # Wrap forecast node to pass plan context via closure
    async def forecast_with_plan(state: FinSightState) -> FinSightState:
        return await forecast_agent_node(state, plan=plan)

    graph.add_node("forecast_agent", forecast_with_plan)
    graph.add_node("report_generator", report_generator_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point("orchestrator")

    # ── Sequential: orchestrator → parallel fan-out ───────────────────────────
    graph.add_edge("orchestrator", "risk_analyst")
    graph.add_edge("orchestrator", "sentiment_agent")
    graph.add_edge("orchestrator", "forecast_agent")

    # ── Parallel convergence → report generator ───────────────────────────────
    graph.add_edge("risk_analyst", "report_generator")
    graph.add_edge("sentiment_agent", "report_generator")
    graph.add_edge("forecast_agent", "report_generator")

    # ── Terminal ──────────────────────────────────────────────────────────────
    graph.add_edge("report_generator", END)

    return graph.compile()
