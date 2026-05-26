from langgraph.graph import StateGraph, END
from graph.state import FinSightState
from agents.orchestrator import orchestrator_node, report_generator_node
from agents.risk_agent import risk_analyst_node
from agents.sentiment_agent import sentiment_agent_node
from agents.forecast_agent import forecast_agent_node

def build_graph():
    graph = StateGraph(FinSightState)

    # Register all nodes
    graph.add_node("orchestrator",      orchestrator_node)
    graph.add_node("risk_analyst",      risk_analyst_node)
    graph.add_node("sentiment_agent",   sentiment_agent_node)
    graph.add_node("forecast_agent",    forecast_agent_node)
    graph.add_node("report_generator",  report_generator_node)

    # Entry point
    graph.set_entry_point("orchestrator")

    # Orchestrator fans out to all three agents in parallel
    graph.add_edge("orchestrator",    "risk_analyst")
    graph.add_edge("orchestrator",    "sentiment_agent")
    graph.add_edge("orchestrator",    "forecast_agent")

    # All three agents feed into report generator
    graph.add_edge("risk_analyst",    "report_generator")
    graph.add_edge("sentiment_agent", "report_generator")
    graph.add_edge("forecast_agent",  "report_generator")

    # Report generator ends the graph
    graph.add_edge("report_generator", END)

    return graph.compile()


# Singleton — import this everywhere
finsight_graph = build_graph()