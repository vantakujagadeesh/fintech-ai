"""
FinSight AI — FastAPI Application Entry Point.
Assembles all routers, configures middleware, and initializes the database.
"""

from __future__ import annotations

import logging
import os

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration

from backend.core.config import settings
from backend.core.db import init_db

# ─── Sentry (init before routes) ─────────────────────────────────────────────

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.2,
        environment=settings.APP_ENV,
    )

# ─── LangSmith tracing ────────────────────────────────────────────────────────

if settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="FinSight AI API",
    description="Multi-tenant Financial Decision Intelligence Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ─── Middleware ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ─── Exception handlers ───────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Our team has been notified."},
    )


# ─── Routers ─────────────────────────────────────────────────────────────────

from backend.api.analyze import router as analyze_router
from backend.api.jobs import router as jobs_router
from backend.api.reports import router as reports_router
from backend.api.upload import router as upload_router
from backend.api.usage import router as usage_router
from backend.api.billing import router as billing_router

app.include_router(analyze_router, tags=["Analysis"])
app.include_router(jobs_router, tags=["Jobs"])
app.include_router(reports_router, tags=["Reports"])
app.include_router(upload_router, tags=["Upload"])
app.include_router(usage_router, tags=["Usage & Auth"])
app.include_router(billing_router, tags=["Billing"])


# ─── Lifecycle ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    logger.info("FinSight AI starting up...")
    await init_db()
    logger.info("Database initialized successfully")


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("FinSight AI shutting down...")


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
    }


@app.get("/", tags=["Root"])
async def root() -> dict:
    return {
        "name": "FinSight AI API",
        "version": "1.0.0",
        "docs": "/docs",
    }
