# backend/analyze.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from core.tenancy import check_quota, get_current_tenant
from core.queue import run_analysis_task
import uuid
import redis

router = APIRouter()

# Redis client for job status polling
r = redis.from_url("redis://localhost:6379", decode_responses=True)


class AnalyzeRequest(BaseModel):
    company: str = Field(..., min_length=1, max_length=255, description="Company name or ticker")
    query: str = Field(..., min_length=5, max_length=2000, description="Investment question")
    ingest_news: bool = Field(default=True, description="Fetch fresh news context")
    ingest_sec: bool = Field(default=False, description="Fetch SEC filings")


@router.post("/analyze", status_code=202)
async def analyze(
    body: AnalyzeRequest,
    tenant: dict = Depends(check_quota),   # quota checked here
):
    job_id = str(uuid.uuid4())

    # Fire the LangGraph pipeline async via Celery
    run_analysis_task.delay(
        job_id=job_id,
        tenant_id=tenant["tenant_id"],
        company=body.company,
        query=body.query,
        pinecone_namespace=tenant["tenant_id"],  # isolated per user
    )

    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}/status")
async def job_status(job_id: str, tenant: dict = Depends(get_current_tenant)):
    """Frontend polls this every 2 seconds for job completion."""
    result = r.get(f"job:{job_id}")
    if not result:
        return {"status": "running", "job_id": job_id}
    import json
    data = json.loads(result)
    return {"status": "complete", "job_id": job_id, "report": data}