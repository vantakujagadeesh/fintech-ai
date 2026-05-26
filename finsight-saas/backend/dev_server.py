"""
FinSight AI — Self-Contained Development Server
================================================
Runs WITHOUT requiring PostgreSQL, Redis, or Celery.
Uses:
  - SQLite (via aiosqlite) for persistence
  - In-memory dict for job status tracking
  - asyncio background tasks instead of Celery
  - Direct OpenAI calls (or mock if no key)

Start with:
  python dev_server.py

Or:
  uvicorn backend.dev_server:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finsight.dev")

# ─── Config ───────────────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("NEXTAUTH_SECRET", os.getenv("JWT_SECRET", "finsight-dev-secret-32chars-minimum"))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

# Plan daily limits
PLAN_LIMITS = {"free": 5, "starter": 50, "pro": 999999}

# ─── In-Memory Stores (replace with SQLite/Redis in prod) ─────────────────────
# users: { email -> { id, email, hashed_password, full_name, plan, is_active, created_at } }
_users: dict[str, dict] = {}
# usage: { tenant_id:date -> int }
_usage: dict[str, int] = {}
# jobs: { job_id -> { status, report?, error? } }
_jobs: dict[str, dict] = {}
# reports: [ { id, tenant_id, job_id, company, ... } ]
_reports: list[dict] = []


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    plan: str


class AnalyzeRequest(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    query: str = Field(..., min_length=5, max_length=2000)
    ingest_news: bool = True
    ingest_sec: bool = False


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str = "queued"
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    report: Optional[dict] = None
    error: Optional[str] = None


class UsageResponse(BaseModel):
    used: int
    limit: int
    plan: str
    date: str
    remaining: int


class CheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str


# ─── JWT Helpers ──────────────────────────────────────────────────────────────

def create_token(user_id: str, email: str, plan: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "email": email, "plan": plan, "exp": int(exp.timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = auth.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    user_id = payload.get("sub")
    email = payload.get("email")
    # Lookup user by ID
    user = next((u for u in _users.values() if u["id"] == user_id), None)
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=401, detail="User not found or deactivated")
    return user


def check_quota(user: dict = Depends(get_current_user)) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    key = f"{user['id']}:{today}"
    used = _usage.get(key, 0)
    limit = PLAN_LIMITS.get(user["plan"], 5)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily quota exceeded ({used}/{limit}). Upgrade your plan.",
        )
    return user


# ─── AI Analysis Pipeline ─────────────────────────────────────────────────────

async def run_analysis_pipeline(
    job_id: str,
    tenant_id: str,
    company: str,
    query: str,
    plan: str,
) -> None:
    """
    Runs the financial analysis pipeline.
    Uses OpenAI if key is available, otherwise returns smart mock data.
    """
    logger.info(f"[{job_id}] Starting analysis: {company} | plan={plan}")
    _jobs[job_id] = {"status": "running", "job_id": job_id}

    try:
        if OPENAI_API_KEY:
            report = await _run_openai_pipeline(job_id, company, query, plan)
        else:
            report = await _run_mock_pipeline(job_id, company, query)

        _jobs[job_id] = {"status": "complete", "job_id": job_id, "report": report}

        # Persist to in-memory reports
        _reports.append({
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "tenant_id": tenant_id,
            "company": company,
            "user_query": query,
            "risk_score": report.get("risk_score"),
            "risk_summary": report.get("risk_summary"),
            "sentiment": report.get("sentiment"),
            "sentiment_confidence": report.get("sentiment_confidence"),
            "forecast": report.get("forecast"),
            "forecast_rationale": report.get("forecast_rationale"),
            "decision_report": report.get("decision_report"),
            "status": "complete",
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"[{job_id}] Analysis complete")

    except Exception as exc:
        logger.error(f"[{job_id}] Pipeline failed: {exc}", exc_info=True)
        _jobs[job_id] = {"status": "failed", "job_id": job_id, "error": str(exc)}


async def _run_openai_pipeline(job_id: str, company: str, query: str, plan: str) -> dict:
    """Real AI pipeline using OpenAI GPT-4o-mini."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    system_prompt = """You are FinSight AI, an elite financial analysis system. 
You analyze companies and provide investment recommendations.
Always respond in valid JSON with these exact keys:
{
  "risk_score": float 0.0-1.0,
  "risk_summary": "2-3 sentence risk analysis",
  "sentiment": "bullish" | "bearish" | "neutral",
  "sentiment_confidence": float 0.0-1.0,
  "forecast": "buy" | "hold" | "sell",
  "forecast_rationale": "2-3 sentence forecast rationale",
  "decision_report": "Comprehensive 3-4 paragraph investment analysis"
}"""

    user_prompt = f"""Analyze {company} and answer: {query}

Consider:
- Current market conditions and sector trends
- Company fundamentals and competitive positioning
- Risk factors (market risk, regulatory, competitive)
- Technical and sentiment indicators

Provide a complete financial analysis."""

    logger.info(f"[{job_id}] Calling OpenAI {OPENAI_MODEL}...")

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    result = json.loads(raw)

    return {
        "job_id": job_id,
        "company": company,
        "user_query": query,
        "risk_score": float(result.get("risk_score", 0.5)),
        "risk_summary": result.get("risk_summary", ""),
        "sentiment": result.get("sentiment", "neutral"),
        "sentiment_confidence": float(result.get("sentiment_confidence", 0.7)),
        "forecast": result.get("forecast", "hold"),
        "forecast_rationale": result.get("forecast_rationale", ""),
        "decision_report": result.get("decision_report", ""),
        "error": None,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _run_mock_pipeline(job_id: str, company: str, query: str) -> dict:
    """Smart mock pipeline when no OpenAI key is available."""
    logger.info(f"[{job_id}] Running mock pipeline (no OpenAI key)")
    await asyncio.sleep(3)  # Simulate processing time

    import random
    risk = round(random.uniform(0.2, 0.8), 2)
    confidence = round(random.uniform(0.6, 0.95), 2)
    sentiment = random.choice(["bullish", "neutral", "bearish"])
    forecast = "buy" if sentiment == "bullish" else ("sell" if sentiment == "bearish" else "hold")

    return {
        "job_id": job_id,
        "company": company,
        "user_query": query,
        "risk_score": risk,
        "risk_summary": (
            f"{company} presents a {'moderate' if risk < 0.6 else 'elevated'} risk profile. "
            f"Key risk factors include market volatility and sector-specific headwinds. "
            f"The overall risk-adjusted return profile appears {'favorable' if risk < 0.5 else 'challenging'}."
        ),
        "sentiment": sentiment,
        "sentiment_confidence": confidence,
        "forecast": forecast,
        "forecast_rationale": (
            f"Based on current market dynamics and {company}'s positioning, "
            f"the {'strong' if forecast == 'buy' else 'weak'} technical and fundamental indicators "
            f"suggest a {forecast.upper()} recommendation with {int(confidence*100)}% confidence."
        ),
        "decision_report": (
            f"## FinSight AI Analysis: {company}\n\n"
            f"**Executive Summary**: Our multi-agent AI pipeline has analyzed {company} "
            f"in response to your query: *\"{query}\"*\n\n"
            f"**Risk Assessment** (Score: {risk:.0%}): The company shows a "
            f"{'manageable' if risk < 0.5 else 'concerning'} risk profile. Market volatility "
            f"and sector dynamics present {'limited' if risk < 0.5 else 'significant'} headwinds "
            f"that investors should monitor closely.\n\n"
            f"**Sentiment Analysis** ({sentiment.upper()}, {confidence:.0%} confidence): "
            f"Market sentiment toward {company} is currently {sentiment}, driven by "
            f"{'positive earnings momentum and strong guidance' if sentiment == 'bullish' else 'mixed signals and cautious investor positioning'}.\n\n"
            f"**Investment Decision**: Based on our comprehensive analysis, we recommend a "
            f"**{forecast.upper()}** position. {'The risk-reward profile is attractive at current levels.' if forecast == 'buy' else 'Investors should exercise caution and wait for clearer signals.' if forecast == 'hold' else 'Consider reducing exposure given current risk factors.'}\n\n"
            f"*Note: This is a demo analysis. Add your OPENAI_API_KEY to backend/.env for real AI analysis.*"
        ),
        "error": None,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── App & Lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FinSight AI Dev Server starting...")
    logger.info(f"OpenAI: {'✓ Key found' if OPENAI_API_KEY else '✗ No key – using mock mode'}")
    logger.info("No PostgreSQL/Redis required – using in-memory stores")
    yield
    logger.info("FinSight AI Dev Server shutting down...")


app = FastAPI(
    title="FinSight AI API (Dev Mode)",
    description="Financial Analysis Platform — Development Server",
    version="2.0.0-dev",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "2.0.0-dev",
        "mode": "development",
        "ai_mode": "openai" if OPENAI_API_KEY else "mock",
        "storage": "in-memory",
    }


@app.get("/")
async def root():
    return {"name": "FinSight AI API", "version": "2.0.0-dev", "docs": "/docs"}


# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.post("/auth/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest):
    if body.email in _users:
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user_id = str(uuid.uuid4())
    _users[body.email] = {
        "id": user_id,
        "email": body.email,
        "hashed_password": hashed,
        "full_name": body.full_name,
        "plan": "free",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    token = create_token(user_id, body.email, "free")
    logger.info(f"Registered user: {body.email}")
    return AuthResponse(access_token=token, user_id=user_id, email=body.email, plan="free")


@app.post("/auth/token", response_model=AuthResponse)
async def login(body: LoginRequest):
    user = _users.get(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not bcrypt.checkpw(body.password.encode(), user["hashed_password"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user["id"], user["email"], user["plan"])
    return AuthResponse(
        access_token=token, user_id=user["id"], email=user["email"], plan=user["plan"]
    )


# ─── Analyze Route ────────────────────────────────────────────────────────────

@app.post("/analyze", response_model=AnalyzeResponse, status_code=202)
async def analyze(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(check_quota),
):
    job_id = str(uuid.uuid4())
    today = datetime.now(timezone.utc).date().isoformat()
    usage_key = f"{user['id']}:{today}"
    _usage[usage_key] = _usage.get(usage_key, 0) + 1
    _jobs[job_id] = {"status": "queued", "job_id": job_id}

    background_tasks.add_task(
        run_analysis_pipeline,
        job_id=job_id,
        tenant_id=user["id"],
        company=body.company,
        query=body.query,
        plan=user["plan"],
    )

    logger.info(f"Queued job {job_id} for {body.company} (user={user['email']})")
    return AnalyzeResponse(
        job_id=job_id,
        status="queued",
        message=f"Analysis queued for {body.company}. Poll /jobs/{job_id}/status.",
    )


# ─── Jobs Route ───────────────────────────────────────────────────────────────

@app.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str, user: dict = Depends(get_current_user)):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        report=job.get("report"),
        error=job.get("error"),
    )


# ─── Reports Routes ───────────────────────────────────────────────────────────

@app.get("/reports")
async def get_reports(
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    tenant_reports = [r for r in _reports if r["tenant_id"] == user["id"]]
    tenant_reports.sort(key=lambda r: r["created_at"], reverse=True)
    start = (page - 1) * page_size
    end = start + page_size
    items = tenant_reports[start:end]
    total = len(tenant_reports)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ─── Usage Route ──────────────────────────────────────────────────────────────

@app.get("/usage", response_model=UsageResponse)
async def get_usage(user: dict = Depends(get_current_user)):
    today = datetime.now(timezone.utc).date().isoformat()
    key = f"{user['id']}:{today}"
    used = _usage.get(key, 0)
    limit = PLAN_LIMITS.get(user["plan"], 5)
    return UsageResponse(
        used=used,
        limit=limit,
        plan=user["plan"],
        date=today,
        remaining=max(0, limit - used),
    )


# ─── Billing Route (Stub) ─────────────────────────────────────────────────────

@app.post("/billing/create-checkout-session")
async def create_checkout(body: CheckoutRequest, user: dict = Depends(get_current_user)):
    # Stub — returns a demo URL. Add Stripe in production.
    return {
        "checkout_url": f"{body.success_url}?plan={body.plan}&demo=true",
        "session_id": f"demo_{uuid.uuid4()}",
    }


# ─── Upload Route (Stub) ──────────────────────────────────────────────────────

@app.post("/upload-portfolio")
async def upload_portfolio(user: dict = Depends(get_current_user)):
    return {
        "message": "Portfolio received (demo mode — no Pinecone configured)",
        "chunks": 12,
        "namespace": user["id"],
        "filename": "portfolio.pdf",
    }


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("  FinSight AI — Development Server")
    print("="*60)
    print(f"  API:  http://localhost:8000")
    print(f"  Docs: http://localhost:8000/docs")
    print(f"  AI Mode: {'OpenAI GPT-4o-mini' if OPENAI_API_KEY else 'Mock (no key)'}")
    print("="*60 + "\n")
    uvicorn.run(
        "backend.dev_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
