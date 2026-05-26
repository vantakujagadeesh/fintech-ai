"""
GET /jobs/{id}/status — Reads job status from Redis.
Frontend polls every 2 seconds until status=complete.
"""

from __future__ import annotations

import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Any

from backend.core.tenancy import TenantContext, get_current_tenant, get_redis

router = APIRouter()


class ReportData(BaseModel):
    job_id: str
    company: str
    user_query: str
    risk_score: Optional[float] = None
    risk_summary: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_confidence: Optional[float] = None
    forecast: Optional[str] = None
    forecast_rationale: Optional[str] = None
    decision_report: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # "queued" | "running" | "complete" | "failed"
    report: Optional[ReportData] = None
    error: Optional[str] = None


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    redis: aioredis.Redis = Depends(get_redis),
) -> JobStatusResponse:
    """
    Read job status from Redis.
    Returns running/complete/failed status with report data when complete.
    """
    key = f"job:{job_id}"
    raw = await redis.get(key)

    if raw is None:
        # Check if it's a valid job_id that just hasn't started yet
        # (Celery task may still be in queue)
        return JobStatusResponse(job_id=job_id, status="queued")

    data = json.loads(raw)
    job_status = data.get("status", "unknown")

    if job_status == "complete":
        report_data = data.get("report", {})
        return JobStatusResponse(
            job_id=job_id,
            status="complete",
            report=ReportData(**report_data),
        )

    elif job_status == "failed":
        return JobStatusResponse(
            job_id=job_id,
            status="failed",
            error=data.get("error", "Unknown error"),
        )

    # running or queued
    return JobStatusResponse(job_id=job_id, status=job_status)
