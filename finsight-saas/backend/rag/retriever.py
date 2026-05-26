"""
Hybrid RAG Retriever — BM25 (keyword) + Dense (semantic) fusion.
Returns top_k=6 documents by default.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain.retrievers import EnsembleRetriever

from backend.core.config import settings
from backend.rag.ingest import get_embeddings, _get_faiss_path

logger = logging.getLogger(__name__)

TOP_K = 6


def get_retriever(namespace: str) -> BaseRetriever:
    """
    Returns a hybrid BM25 + dense retriever for the given tenant namespace.
    Falls back to dense-only if BM25 has insufficient docs.
    Uses FAISS in dev, Pinecone in production.
    """
    if settings.is_production and settings.PINECONE_API_KEY:
        return _build_pinecone_retriever(namespace)
    else:
        return _build_faiss_retriever(namespace)


def _build_faiss_retriever(namespace: str) -> BaseRetriever:
    """Build hybrid retriever backed by local FAISS index."""
    embeddings = get_embeddings()
    faiss_path = _get_faiss_path(namespace)
    index_file = os.path.join(faiss_path, "index.faiss")

    if not os.path.exists(index_file):
        logger.warning(f"[Retriever] No FAISS index for namespace={namespace}, using empty retriever")
        return _empty_retriever()

    db = FAISS.load_local(faiss_path, embeddings, allow_dangerous_deserialization=True)
    dense_retriever = db.as_retriever(search_kwargs={"k": TOP_K})

    # Try to build BM25 from stored documents
    try:
        all_docs = list(db.docstore._dict.values())
        if len(all_docs) >= 2:
            bm25_retriever = BM25Retriever.from_documents(all_docs)
            bm25_retriever.k = TOP_K

            # Ensemble: 40% BM25 + 60% dense
            hybrid = EnsembleRetriever(
                retrievers=[bm25_retriever, dense_retriever],
                weights=[0.4, 0.6],
            )
            logger.info(f"[Retriever] Hybrid retriever built for namespace={namespace}")
            return hybrid
    except Exception as exc:
        logger.warning(f"[Retriever] BM25 init failed, using dense only: {exc}")

    return dense_retriever


def _build_pinecone_retriever(namespace: str) -> BaseRetriever:
    """Build dense retriever backed by Pinecone for production."""
    from langchain_pinecone import PineconeVectorStore
    from pinecone import Pinecone

    embeddings = get_embeddings()
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX)

    vectorstore = PineconeVectorStore(
        index=index,
        embedding=embeddings,
        namespace=namespace,
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
    logger.info(f"[Retriever] Pinecone retriever built for namespace={namespace}")
    return retriever


class _EmptyRetriever(BaseRetriever):
    """Fallback retriever that returns no documents."""

    async def _aget_relevant_documents(self, query: str) -> list[Document]:
        return []

    def _get_relevant_documents(self, query: str) -> list[Document]:
        return []


def _empty_retriever() -> _EmptyRetriever:
    return _EmptyRetriever()
