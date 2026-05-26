from graph.builder 
import finsight_graph

def run_query(company: str, question: str) -> str:
    initial_state = {
        "user_query": question,
        "company": company,
        "retrieved_docs": [],
        "risk_score": None,
        "risk_summary": None,
        "sentiment": None,
        "sentiment_confidence": None,
        "forecast": None,
        "forecast_rationale": None,
        "decision_report": None,
        "error": None,
    }

    final_state = finsight_graph.invoke(initial_state)
    return final_state["decision_report"]


if __name__ == "__main__":
    report = run_query(
        company="AAPL",
        question="Should I hold Apple stock given current market conditions?"
    )
    print(report)