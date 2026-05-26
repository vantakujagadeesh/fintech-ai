"""
Orchestrator node — fetches RAG context from FAISS/Pinecone
and populates state.retrieved_docs before parallel agents run.
"""

from __future__ import annotations

import logging

from backend.agents.graph.state import FinSightState
from backend.rag.retriever import get_retriever

logger = logging.getLogger(__name__)


async def orchestrator_node(state: FinSightState) -> FinSightState:
    """
    1. Build hybrid retriever for the tenant's namespace.
    2. Run retrieval against user_query + company context.
    3. Populate retrieved_docs with top-k chunks.
    """
    try:
        retriever = get_retriever(namespace=state["namespace"])
        query = f"{state['company']}: {state['user_query']}"
        docs = await retriever.aget_relevant_documents(query)
        retrieved_docs = [doc.page_content for doc in docs]

        logger.info(
            f"[Orchestrator] Retrieved {len(retrieved_docs)} docs "
            f"for namespace={state['namespace']}"
        )

        return {**state, "retrieved_docs": retrieved_docs}

    except Exception as exc:
        logger.error(f"[Orchestrator] Retrieval failed: {exc}", exc_info=True)
        # Continue with empty docs rather than crashing the pipeline
        return {**state, "retrieved_docs": [], "error": f"Retrieval error: {exc}"}
