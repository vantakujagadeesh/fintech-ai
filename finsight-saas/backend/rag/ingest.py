"""
RAG Ingest Pipeline.
PDF → chunks → embeddings → FAISS (dev) / Pinecone (prod)
Also supports SEC EDGAR and NewsAPI ingestion.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Optional

import httpx
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from backend.core.config import settings

logger = logging.getLogger(__name__)

# ─── Embedding model (shared singleton) ──────────────────────────────────────

_embeddings: HuggingFaceEmbeddings | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


# ─── Text splitter ────────────────────────────────────────────────────────────

def get_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=64,
        length_function=len,
        separators=["\n\n", "\n", ".", " ", ""],
    )


# ─── PDF Ingest ───────────────────────────────────────────────────────────────

async def ingest_pdf(
    file_bytes: bytes,
    filename: str,
    namespace: str,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Process a PDF file:
    1. Parse PDF pages
    2. Split into chunks
    3. Embed with sentence-transformers
    4. Store in FAISS (dev) or Pinecone (prod)
    Returns: {"chunks": int, "namespace": str}
    """
    logger.info(f"[Ingest] Starting PDF ingest: {filename} → namespace={namespace}")

    # Write bytes to temp file for PyPDFLoader
    tmp_path = Path(f"/tmp/{namespace}_{filename}")
    tmp_path.write_bytes(file_bytes)

    try:
        loader = PyPDFLoader(str(tmp_path))
        pages = loader.load()

        splitter = get_text_splitter()
        chunks = splitter.split_documents(pages)

        # Add metadata
        for chunk in chunks:
            chunk.metadata.update({
                "source": filename,
                "namespace": namespace,
                **(metadata or {}),
            })

        embeddings = get_embeddings()

        if settings.is_production and settings.PINECONE_API_KEY:
            await _store_in_pinecone(chunks, namespace, embeddings)
        else:
            _store_in_faiss(chunks, namespace, embeddings)

        logger.info(f"[Ingest] PDF ingest complete: {len(chunks)} chunks for namespace={namespace}")
        return {"chunks": len(chunks), "namespace": namespace, "source": filename}

    finally:
        tmp_path.unlink(missing_ok=True)


# ─── SEC EDGAR Ingest ─────────────────────────────────────────────────────────

async def ingest_sec_filings(company_ticker: str, namespace: str) -> dict:
    """
    Fetch latest 10-K and 10-Q from SEC EDGAR API.
    Ingests text content into the vector store.
    """
    logger.info(f"[Ingest] Fetching SEC filings for {company_ticker}")

    # SEC EDGAR full-text search API
    search_url = "https://efts.sec.gov/LATEST/search-index?q={}&dateRange=custom&startdt=2023-01-01&forms=10-K,10-Q"
    headers = {"User-Agent": "FinSightAI contact@finsight.ai"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Search for company filings
            resp = await client.get(
                f"https://efts.sec.gov/LATEST/search-index?q=%22{company_ticker}%22&forms=10-K,10-Q",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        filings = data.get("hits", {}).get("hits", [])[:3]  # top 3 filings
        documents: list[Document] = []
        splitter = get_text_splitter()

        for filing in filings:
            source = filing.get("_source", {})
            file_text = source.get("file_text", "")[:10000]  # limit to 10k chars
            if file_text:
                doc = Document(
                    page_content=file_text,
                    metadata={
                        "source": "sec_edgar",
                        "ticker": company_ticker,
                        "form_type": source.get("form_type", ""),
                        "filed_at": source.get("period_of_report", ""),
                        "namespace": namespace,
                    },
                )
                chunks = splitter.split_documents([doc])
                documents.extend(chunks)

        if documents:
            embeddings = get_embeddings()
            if settings.is_production and settings.PINECONE_API_KEY:
                await _store_in_pinecone(documents, namespace, embeddings)
            else:
                _store_in_faiss(documents, namespace, embeddings)

        logger.info(f"[Ingest] SEC ingest complete: {len(documents)} chunks for {company_ticker}")
        return {"chunks": len(documents), "source": "sec_edgar", "ticker": company_ticker}

    except Exception as exc:
        logger.error(f"[Ingest] SEC filing fetch failed: {exc}", exc_info=True)
        return {"chunks": 0, "source": "sec_edgar", "error": str(exc)}


# ─── NewsAPI Ingest ───────────────────────────────────────────────────────────

async def ingest_news(company: str, namespace: str) -> dict:
    """Fetch recent news articles about the company and ingest into vector store."""
    if not settings.NEWS_API_KEY:
        logger.warning("[Ingest] NEWS_API_KEY not set, skipping news ingest")
        return {"chunks": 0, "source": "newsapi"}

    logger.info(f"[Ingest] Fetching news for {company}")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": company,
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                    "language": "en",
                    "apiKey": settings.NEWS_API_KEY,
                },
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])

        documents: list[Document] = []
        splitter = get_text_splitter()

        for article in articles:
            content = article.get("content") or article.get("description") or ""
            if content and len(content) > 100:
                doc = Document(
                    page_content=f"HEADLINE: {article.get('title', '')}\n\n{content}",
                    metadata={
                        "source": "newsapi",
                        "company": company,
                        "published_at": article.get("publishedAt", ""),
                        "url": article.get("url", ""),
                        "namespace": namespace,
                    },
                )
                chunks = splitter.split_documents([doc])
                documents.extend(chunks)

        if documents:
            embeddings = get_embeddings()
            if settings.is_production and settings.PINECONE_API_KEY:
                await _store_in_pinecone(documents, namespace, embeddings)
            else:
                _store_in_faiss(documents, namespace, embeddings)

        logger.info(f"[Ingest] News ingest complete: {len(documents)} chunks for {company}")
        return {"chunks": len(documents), "source": "newsapi", "company": company}

    except Exception as exc:
        logger.error(f"[Ingest] News fetch failed: {exc}", exc_info=True)
        return {"chunks": 0, "source": "newsapi", "error": str(exc)}


# ─── Storage backends ─────────────────────────────────────────────────────────

def _get_faiss_path(namespace: str) -> str:
    path = f"/tmp/finsight_faiss/{namespace}"
    os.makedirs(path, exist_ok=True)
    return path


def _store_in_faiss(documents: list[Document], namespace: str, embeddings: HuggingFaceEmbeddings) -> None:
    """Store documents in FAISS index for the given namespace."""
    faiss_path = _get_faiss_path(namespace)
    index_file = os.path.join(faiss_path, "index.faiss")

    if os.path.exists(index_file):
        # Load existing and merge
        db = FAISS.load_local(faiss_path, embeddings, allow_dangerous_deserialization=True)
        db.add_documents(documents)
    else:
        db = FAISS.from_documents(documents, embeddings)

    db.save_local(faiss_path)
    logger.debug(f"[Ingest] FAISS saved: {faiss_path}")


async def _store_in_pinecone(
    documents: list[Document],
    namespace: str,
    embeddings: HuggingFaceEmbeddings,
) -> None:
    """Store documents in Pinecone with namespace isolation per tenant."""
    from langchain_pinecone import PineconeVectorStore
    from pinecone import Pinecone

    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX)

    vectorstore = PineconeVectorStore(
        index=index,
        embedding=embeddings,
        namespace=namespace,
    )
    await vectorstore.aadd_documents(documents)
    logger.debug(f"[Ingest] Pinecone stored: {len(documents)} docs in namespace={namespace}")
