# agents/forecast_agent.py
# This is where your fine-tuned LLaMA plugs in (week 5-6)
# For now, uses OpenAI as a placeholder
from langchain_openai import ChatOpenAI
from graph.state import FinSightState

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

def forecast_agent_node(state: FinSightState) -> dict:
    """Generates a forward-looking forecast."""
    prompt = f"""You are a financial forecasting model.
Company: {state['company']}
Current risk score: {state.get('risk_score', 'unknown')}
Current sentiment: {state.get('sentiment', 'unknown')}
User question: {state['user_query']}

Provide a short-term forecast (30-day outlook).
Format EXACTLY as:
FORECAST: buy|hold|sell
RATIONALE: <2 sentence explanation>"""

    response = llm.invoke(prompt)
    lines = response.content.strip().split("\n")

    forecast = "hold"
    rationale = "Insufficient data for a confident forecast."
    for line in lines:
        if line.startswith("FORECAST:"):
            forecast = line.replace("FORECAST:", "").strip().lower()
        if line.startswith("RATIONALE:"):
            rationale = line.replace("RATIONALE:", "").strip()

    return {
        "forecast": forecast,
        "forecast_rationale": rationale
    }