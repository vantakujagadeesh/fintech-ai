"""
Celery task queue for async LangGraph analysis jobs.
Task writes results to Redis with 1hr TTL.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import redis
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.core.config import settings

logger = logging.getLogger(__name__)

# ─── Celery App ───────────────────────────────────────────────────────────────

celery_app = Celery(
    "finsight",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

# ─── Sync Redis client for Celery tasks ───────────────────────────────────────

_sync_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

# ─── Sync SQLAlchemy engine for Celery tasks ──────────────────────────────────
# Celery runs in a sync context, so we use the sync engine here.
_sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
_sync_engine = create_engine(_sync_db_url, pool_pre_ping=True)


def _set_job_status(job_id: str, payload: dict, ttl: int = 3600) -> None:
    key = f"job:{job_id}"
    _sync_redis.set(key, json.dumps(payload), ex=ttl)


# ─── Celery Task ──────────────────────────────────────────────────────────────

@celery_app.task(
    name="finsight.run_analysis_task",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def run_analysis_task(
    self,
    job_id: str,
    tenant_id: str,
    company: str,
    query: str,
    namespace: str,
    plan: str = "free",
) -> dict:
    """
    Async Celery task that runs the full LangGraph agent pipeline.
    Writes status updates to Redis key job:{job_id}.
    On completion, writes full report and updates PostgreSQL.
    """
    logger.info(f"[Task {job_id}] Starting analysis for {company} (tenant={tenant_id})")

    # Mark job as running
    _set_job_status(job_id, {"status": "running", "job_id": job_id})

    try:
        # Import here to avoid circular imports at module load
        from backend.agents.graph.builder import build_graph
        from backend.agents.graph.state import FinSightState

        # Build and run the LangGraph pipeline
        graph = build_graph(plan=plan)

        initial_state: FinSightState = {
            "user_query": query,
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
            "namespace": namespace,
        }

        final_state = graph.invoke(initial_state)

        report = {
            "job_id": job_id,
            "company": company,
            "user_query": query,
            "risk_score": final_state.get("risk_score"),
            "risk_summary": final_state.get("risk_summary"),
            "sentiment": final_state.get("sentiment"),
            "sentiment_confidence": final_state.get("sentiment_confidence"),
            "forecast": final_state.get("forecast"),
            "forecast_rationale": final_state.get("forecast_rationale"),
            "decision_report": final_state.get("decision_report"),
            "error": final_state.get("error"),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist to Redis
        _set_job_status(job_id, {"status": "complete", "report": report})

        # Persist to PostgreSQL
        _persist_report_to_db(job_id=job_id, tenant_id=tenant_id, report=report)

        logger.info(f"[Task {job_id}] Completed successfully")
        return report

    except Exception as exc:
        logger.error(f"[Task {job_id}] Failed: {exc}", exc_info=True)
        error_payload = {
            "status": "failed",
            "job_id": job_id,
            "error": str(exc),
        }
        _set_job_status(job_id, error_payload)

        # Retry if possible
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return error_payload


def _persist_report_to_db(job_id: str, tenant_id: str, report: dict) -> None:
    """Write the completed report to PostgreSQL."""
    try:
        from backend.core.db import Report

        with Session(_sync_engine) as session:
            db_report = session.query(Report).filter_by(job_id=job_id).first()
            if db_report:
                db_report.status = "complete"
                db_report.risk_score = report.get("risk_score")
                db_report.risk_summary = report.get("risk_summary")
                db_report.sentiment = report.get("sentiment")
                db_report.sentiment_confidence = report.get("sentiment_confidence")
                db_report.forecast = report.get("forecast")
                db_report.forecast_rationale = report.get("forecast_rationale")
                db_report.decision_report = report.get("decision_report")
                db_report.error = report.get("error")
                db_report.completed_at = datetime.now(timezone.utc)
                session.commit()
    except Exception as exc:
        logger.error(f"Failed to persist report {job_id} to DB: {exc}", exc_info=True)
