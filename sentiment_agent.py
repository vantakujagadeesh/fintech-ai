# agents/sentiment_agent.py
from langchain_openai import ChatOpenAI
from graph.state import FinSightState

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def sentiment_agent_node(state: FinSightState) -> dict:
    """Runs sentiment analysis on news and filings."""
    docs_context = "\n\n".join(state["retrieved_docs"][3:6])

    prompt = f"""You are a financial sentiment analyst.
Company: {state['company']}
Relevant news and filings:
{docs_context}

Classify the overall market sentiment for this company.
Format EXACTLY as:
SENTIMENT: bullish|bearish|neutral
CONFIDENCE: <float 0.0-1.0>"""

    response = llm.invoke(prompt)
    lines = response.content.strip().split("\n")

    sentiment = "neutral"
    confidence = 0.5
    for line in lines:
        if line.startswith("SENTIMENT:"):
            sentiment = line.replace("SENTIMENT:", "").strip().lower()
        if line.startswith("CONFIDENCE:"):
            try:
                confidence = float(line.replace("CONFIDENCE:", "").strip())
            except ValueError:
                pass

    return {
        "sentiment": sentiment,
        "sentiment_confidence": confidence
    }