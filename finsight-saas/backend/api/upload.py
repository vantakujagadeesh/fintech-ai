"""
POST /upload-portfolio — Accepts PDF upload, runs RAG ingest.
Stores in Pinecone namespace=tenant_id for isolation.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.core.tenancy import TenantContext, get_current_tenant
from backend.rag.ingest import ingest_news, ingest_pdf, ingest_sec_filings

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE_MB = 20
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


class UploadResponse(BaseModel):
    message: str
    chunks: int
    namespace: str
    filename: str


@router.post("/upload-portfolio", response_model=UploadResponse, status_code=201)
async def upload_portfolio(
    file: UploadFile = File(..., description="PDF portfolio file (max 20MB)"),
    tenant: TenantContext = Depends(get_current_tenant),
) -> UploadResponse:
    """
    Accept a PDF portfolio upload, process it through the RAG pipeline,
    and store embeddings in the tenant's isolated namespace.
    """
    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Only PDF files are accepted. Got: {file.content_type}",
        )

    # Read file bytes
    file_bytes = await file.read()
    file_size_mb = len(file_bytes) / (1024 * 1024)

    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({file_size_mb:.1f}MB). Maximum is {MAX_FILE_SIZE_MB}MB.",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    logger.info(
        f"[Upload] Processing PDF: {file.filename} ({file_size_mb:.1f}MB) "
        f"for tenant={tenant.tenant_id}"
    )

    # Run ingest pipeline
    result = await ingest_pdf(
        file_bytes=file_bytes,
        filename=file.filename or "portfolio.pdf",
        namespace=tenant.tenant_id,
        metadata={
            "tenant_id": tenant.tenant_id,
            "plan": tenant.plan,
        },
    )

    return UploadResponse(
        message="Portfolio ingested successfully. You can now run analyses.",
        chunks=result["chunks"],
        namespace=tenant.tenant_id,
        filename=file.filename or "portfolio.pdf",
    )


class IngestContextRequest(BaseModel):
    company: str
    ingest_news: bool = True
    ingest_sec: bool = False


class IngestContextResponse(BaseModel):
    message: str
    news_chunks: int
    sec_chunks: int


@router.post("/ingest-context", response_model=IngestContextResponse)
async def ingest_company_context(
    body: IngestContextRequest,
    tenant: TenantContext = Depends(get_current_tenant),
) -> IngestContextResponse:
    """
    Pre-ingest company data (news + SEC filings) into the tenant's namespace.
    Call this before running analysis for better RAG context.
    """
    news_chunks = 0
    sec_chunks = 0

    if body.ingest_news:
        result = await ingest_news(body.company, tenant.tenant_id)
        news_chunks = result.get("chunks", 0)

    if body.ingest_sec:
        result = await ingest_sec_filings(body.company, tenant.tenant_id)
        sec_chunks = result.get("chunks", 0)

    return IngestContextResponse(
        message=f"Context ingested for {body.company}",
        news_chunks=news_chunks,
        sec_chunks=sec_chunks,
    )
