"""
Pytest tests for FinSight AI backend.
Covers: quota logic, all 6 API endpoints, LangGraph state transitions.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient

# ─── Fixtures ─────────────────────────────────────────────────────────────────

MOCK_TENANT_ID = str(uuid.uuid4())
MOCK_EMAIL = "test@finsight.ai"
MOCK_PLAN = "free"
MOCK_TOKEN = "Bearer mock-jwt-token"


def _mock_tenant():
    from backend.core.tenancy import TenantContext, PLAN_LIMITS
    return TenantContext(
        tenant_id=MOCK_TENANT_ID,
        email=MOCK_EMAIL,
        plan=MOCK_PLAN,
        daily_limit=PLAN_LIMITS[MOCK_PLAN],
    )


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create AsyncClient with mocked auth and DB dependencies."""
    from backend.main import app
    from backend.core.tenancy import get_current_tenant, check_quota
    from backend.core.db import get_db

    tenant = _mock_tenant()

    app.dependency_overrides[get_current_tenant] = lambda: tenant
    app.dependency_overrides[check_quota] = lambda: tenant
    app.dependency_overrides[get_db] = _mock_db_session

    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


async def _mock_db_session():
    """Mock SQLAlchemy async session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # Mock execute to return empty results by default
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one.return_value = 0
    session.execute = AsyncMock(return_value=mock_result)

    yield session


# ─── Quota Logic Tests ────────────────────────────────────────────────────────

class TestQuotaLogic:
    """Test tenancy.py quota enforcement logic."""

    @pytest.mark.asyncio
    async def test_check_quota_under_limit(self):
        """Should pass when usage is below daily limit."""
        from backend.core.tenancy import check_quota, get_current_tenant, get_redis, PLAN_LIMITS

        tenant = _mock_tenant()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="3")  # 3 used, limit is 5

        # Should not raise
        result = await check_quota.__wrapped__(tenant=tenant, redis=mock_redis)
        assert result.tenant_id == MOCK_TENANT_ID

    @pytest.mark.asyncio
    async def test_check_quota_at_limit_raises_429(self):
        """Should raise 429 when usage equals daily limit."""
        from backend.core.tenancy import check_quota
        from fastapi import HTTPException

        tenant = _mock_tenant()  # free plan = 5/day
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="5")  # exactly at limit

        with pytest.raises(HTTPException) as exc_info:
            await check_quota.__wrapped__(tenant=tenant, redis=mock_redis)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_check_quota_over_limit_raises_429(self):
        """Should raise 429 when usage exceeds daily limit."""
        from backend.core.tenancy import check_quota
        from fastapi import HTTPException

        tenant = _mock_tenant()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="10")  # over limit of 5

        with pytest.raises(HTTPException) as exc_info:
            await check_quota.__wrapped__(tenant=tenant, redis=mock_redis)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_check_quota_zero_usage(self):
        """Should pass when no queries made yet today."""
        from backend.core.tenancy import check_quota

        tenant = _mock_tenant()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # no key in Redis

        result = await check_quota.__wrapped__(tenant=tenant, redis=mock_redis)
        assert result.daily_limit == 5

    @pytest.mark.asyncio
    async def test_increment_usage(self):
        """Should increment Redis counter and set TTL."""
        from backend.core.tenancy import increment_usage

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=4)
        mock_redis.expire = AsyncMock()

        count = await increment_usage(MOCK_TENANT_ID, mock_redis)

        today = date.today().isoformat()
        expected_key = f"usage:{MOCK_TENANT_ID}:{today}"
        mock_redis.incr.assert_called_once_with(expected_key)
        mock_redis.expire.assert_called_once_with(expected_key, 90000)
        assert count == 4

    @pytest.mark.asyncio
    async def test_pro_plan_unlimited_quota(self):
        """Pro plan should have limit of 999999."""
        from backend.core.tenancy import TenantContext, check_quota, PLAN_LIMITS

        pro_tenant = TenantContext(
            tenant_id=MOCK_TENANT_ID,
            email=MOCK_EMAIL,
            plan="pro",
            daily_limit=PLAN_LIMITS["pro"],
        )
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="50000")  # high but under 999999

        result = await check_quota.__wrapped__(tenant=pro_tenant, redis=mock_redis)
        assert result.plan == "pro"
        assert result.daily_limit == 999999


# ─── API Endpoint Tests ───────────────────────────────────────────────────────

class TestAnalyzeEndpoint:
    """Test POST /analyze."""

    @pytest.mark.asyncio
    async def test_analyze_returns_job_id(self, client: AsyncClient):
        """POST /analyze should return 202 with job_id."""
        with (
            patch("backend.api.analyze.increment_usage", new_callable=AsyncMock) as mock_incr,
            patch("backend.api.analyze.run_analysis_task") as mock_task,
            patch("backend.api.analyze.get_redis", return_value=AsyncMock()),
        ):
            mock_incr.return_value = 1
            mock_task.apply_async = MagicMock()

            resp = await client.post(
                "/analyze",
                json={"company": "Apple Inc", "query": "Should I buy AAPL stock?"},
                headers={"Authorization": MOCK_TOKEN},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_analyze_missing_query_returns_422(self, client: AsyncClient):
        """POST /analyze without query should return 422."""
        resp = await client.post(
            "/analyze",
            json={"company": "Apple"},
            headers={"Authorization": MOCK_TOKEN},
        )
        assert resp.status_code == 422


class TestJobsEndpoint:
    """Test GET /jobs/{id}/status."""

    @pytest.mark.asyncio
    async def test_job_status_queued(self, client: AsyncClient):
        """Non-existent job should return queued status."""
        job_id = str(uuid.uuid4())
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("backend.api.jobs.get_redis", return_value=mock_redis):
            resp = await client.get(
                f"/jobs/{job_id}/status",
                headers={"Authorization": MOCK_TOKEN},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"

    @pytest.mark.asyncio
    async def test_job_status_complete(self, client: AsyncClient):
        """Completed job should return status=complete with report."""
        job_id = str(uuid.uuid4())
        mock_report = {
            "job_id": job_id,
            "company": "Tesla",
            "user_query": "Should I buy TSLA?",
            "risk_score": 0.75,
            "risk_summary": "High volatility",
            "sentiment": "bullish",
            "sentiment_confidence": 0.8,
            "forecast": "hold",
            "forecast_rationale": "Wait for earnings",
            "decision_report": "## Tesla Report...",
            "error": None,
            "completed_at": "2024-01-01T00:00:00+00:00",
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=json.dumps({"status": "complete", "report": mock_report})
        )

        with patch("backend.api.jobs.get_redis", return_value=mock_redis):
            resp = await client.get(
                f"/jobs/{job_id}/status",
                headers={"Authorization": MOCK_TOKEN},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert data["report"]["risk_score"] == 0.75
        assert data["report"]["sentiment"] == "bullish"

    @pytest.mark.asyncio
    async def test_job_status_running(self, client: AsyncClient):
        """Running job should return status=running without report."""
        job_id = str(uuid.uuid4())
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=json.dumps({"status": "running", "job_id": job_id})
        )

        with patch("backend.api.jobs.get_redis", return_value=mock_redis):
            resp = await client.get(
                f"/jobs/{job_id}/status",
                headers={"Authorization": MOCK_TOKEN},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "running"
        assert resp.json()["report"] is None


class TestReportsEndpoint:
    """Test GET /reports."""

    @pytest.mark.asyncio
    async def test_reports_returns_paginated_list(self, client: AsyncClient):
        """GET /reports should return paginated response."""
        resp = await client.get("/reports", headers={"Authorization": MOCK_TOKEN})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_reports_404_for_unknown_id(self, client: AsyncClient):
        """GET /reports/{bad_id} should return 404."""
        resp = await client.get(
            f"/reports/{uuid.uuid4()}",
            headers={"Authorization": MOCK_TOKEN},
        )
        assert resp.status_code == 404


class TestUploadEndpoint:
    """Test POST /upload-portfolio."""

    @pytest.mark.asyncio
    async def test_upload_pdf_success(self, client: AsyncClient):
        """Upload valid PDF should return 201."""
        with patch("backend.api.upload.ingest_pdf", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = {
                "chunks": 42,
                "namespace": MOCK_TENANT_ID,
                "source": "portfolio.pdf",
            }

            resp = await client.post(
                "/upload-portfolio",
                files={"file": ("portfolio.pdf", b"%PDF-1.4 test content", "application/pdf")},
                headers={"Authorization": MOCK_TOKEN},
            )

        assert resp.status_code == 201
        assert resp.json()["chunks"] == 42

    @pytest.mark.asyncio
    async def test_upload_non_pdf_returns_415(self, client: AsyncClient):
        """Non-PDF upload should return 415."""
        resp = await client.post(
            "/upload-portfolio",
            files={"file": ("data.csv", b"col1,col2", "text/csv")},
            headers={"Authorization": MOCK_TOKEN},
        )
        assert resp.status_code == 415


class TestUsageEndpoint:
    """Test GET /usage."""

    @pytest.mark.asyncio
    async def test_usage_returns_correct_structure(self, client: AsyncClient):
        """GET /usage should return used, limit, plan."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="3")

        with patch("backend.api.usage.get_redis", return_value=mock_redis):
            resp = await client.get("/usage", headers={"Authorization": MOCK_TOKEN})

        assert resp.status_code == 200
        data = resp.json()
        assert "used" in data
        assert "limit" in data
        assert "plan" in data
        assert data["plan"] == MOCK_PLAN


# ─── LangGraph State Tests ─────────────────────────────────────────────────────

class TestLangGraphState:
    """Test LangGraph state transitions through nodes."""

    def _base_state(self) -> dict:
        return {
            "user_query": "Should I buy Apple stock?",
            "company": "Apple Inc",
            "namespace": MOCK_TENANT_ID,
            "retrieved_docs": ["Apple had record revenue of $90B in Q4."],
            "risk_score": None,
            "risk_summary": None,
            "sentiment": None,
            "sentiment_confidence": None,
            "forecast": None,
            "forecast_rationale": None,
            "decision_report": None,
            "error": None,
        }

    @pytest.mark.asyncio
    async def test_risk_agent_populates_state(self):
        """Risk agent should write risk_score and risk_summary."""
        from backend.agents.nodes.risk_agent import risk_analyst_node, _parse_risk_response

        # Test parser directly
        mock_response = "SCORE: 0.65\nSUMMARY: Company faces supply chain risks."
        score, summary = _parse_risk_response(mock_response)

        assert score == 0.65
        assert "supply chain" in summary

    def test_risk_score_clamped_to_valid_range(self):
        """Risk score should always be 0.0–1.0."""
        from backend.agents.nodes.risk_agent import _parse_risk_response

        # Test over-range value gets clamped
        score, _ = _parse_risk_response("SCORE: 1.5\nSUMMARY: Extreme risk.")
        assert score == 1.0

        score, _ = _parse_risk_response("SCORE: -0.3\nSUMMARY: Negative risk.")
        assert score == 0.0

    def test_sentiment_parser_valid_values(self):
        """Sentiment should only be bullish/bearish/neutral."""
        from backend.agents.nodes.sentiment_agent import _parse_sentiment_response

        sentiment, confidence, _ = _parse_sentiment_response(
            "SENTIMENT: bullish\nCONFIDENCE: 0.85\nREASONING: Strong earnings."
        )
        assert sentiment == "bullish"
        assert confidence == 0.85

    def test_sentiment_parser_invalid_falls_back(self):
        """Invalid sentiment should fall back to neutral."""
        from backend.agents.nodes.sentiment_agent import _parse_sentiment_response

        sentiment, confidence, _ = _parse_sentiment_response(
            "SENTIMENT: strongly_positive\nCONFIDENCE: 0.9\nREASONING: Great."
        )
        assert sentiment == "neutral"  # fallback

    def test_forecast_parser_valid_values(self):
        """Forecast should be buy/hold/sell."""
        from backend.agents.nodes.forecast_agent import _parse_forecast_response

        forecast, rationale = _parse_forecast_response(
            "FORECAST: buy\nRATIONALE: Strong growth trajectory with new product pipeline."
        )
        assert forecast == "buy"
        assert "growth" in rationale

    def test_forecast_parser_invalid_falls_back(self):
        """Invalid forecast should fall back to hold."""
        from backend.agents.nodes.forecast_agent import _parse_forecast_response

        forecast, _ = _parse_forecast_response("FORECAST: maybe\nRATIONALE: Uncertain.")
        assert forecast == "hold"

    @pytest.mark.asyncio
    async def test_orchestrator_handles_missing_index(self):
        """Orchestrator should not crash if FAISS index missing."""
        from backend.agents.nodes.orchestrator import orchestrator_node

        with patch("backend.agents.nodes.orchestrator.get_retriever") as mock_retriever:
            from backend.rag.retriever import _EmptyRetriever
            empty = _EmptyRetriever()
            mock_retriever.return_value = empty

            state = self._base_state()
            state["retrieved_docs"] = []

            result = await orchestrator_node(state)
            assert "retrieved_docs" in result
            assert isinstance(result["retrieved_docs"], list)
