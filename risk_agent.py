# agents/risk_agent.py
from langchain_openai import ChatOpenAI
from graph.state import FinSightState

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def risk_analyst_node(state: FinSightState) -> dict:
    """Analyzes financial risk from retrieved docs."""
    docs_context = "\n\n".join(state["retrieved_docs"][:3])

    prompt = f"""You are a financial risk analyst.
Company: {state['company']}
User question: {state['user_query']}

Relevant documents:
{docs_context}

Analyze the financial risk. Return:
1. A risk score from 0.0 (very low risk) to 1.0 (very high risk)
2. A 2-sentence risk summary

Format your response EXACTLY as:
SCORE: <float>
SUMMARY: <text>"""

    response = llm.invoke(prompt)
    lines = response.content.strip().split("\n")

    score = 0.5
    summary = "Risk analysis unavailable."
    for line in lines:
        if line.startswith("SCORE:"):
            try:
                score = float(line.replace("SCORE:", "").strip())
            except ValueError:
                pass
        if line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "").strip()

    return {
        "risk_score": score,
        "risk_summary": summary
    }