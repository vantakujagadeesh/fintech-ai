"""
GET /usage — Returns today's query usage vs plan limit.
POST /auth/register + POST /auth/token for JWT issuance.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt
import redis.asyncio as aioredis

from backend.core.db import User, get_db
from backend.core.tenancy import (
    TenantContext,
    get_current_tenant,
    get_redis,
    get_usage,
    PLAN_LIMITS,
    create_access_token,
)

router = APIRouter()


class UsageResponse(BaseModel):
    used: int
    limit: int
    plan: str
    date: str
    remaining: int


@router.get("/usage", response_model=UsageResponse)
async def get_current_usage(
    tenant: TenantContext = Depends(get_current_tenant),
    redis: aioredis.Redis = Depends(get_redis),
) -> UsageResponse:
    """Return today's query usage for the current tenant."""
    usage_data = await get_usage(tenant.tenant_id, redis)
    used = usage_data["used"]
    limit = tenant.daily_limit

    return UsageResponse(
        used=used,
        limit=limit,
        plan=tenant.plan,
        date=usage_data["date"],
        remaining=max(0, limit - used),
    )


# ─── Auth endpoints ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    plan: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new user with email/password. Returns JWT."""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash password
    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    user = User(
        email=body.email,
        hashed_password=hashed,
        full_name=body.full_name,
        plan="free",
    )
    db.add(user)
    await db.flush()  # get the generated ID

    token = create_access_token(
        tenant_id=user.id,
        email=user.email,
        plan=user.plan,
    )

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        plan=user.plan,
    )


@router.post("/auth/token", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Login with email/password. Returns JWT."""
    result = await db.execute(select(User).where(User.email == body.email, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not bcrypt.checkpw(body.password.encode(), user.hashed_password.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        tenant_id=user.id,
        email=user.email,
        plan=user.plan,
    )

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        plan=user.plan,
    )
