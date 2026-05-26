"""
JWT decode middleware + quota enforcement.
Every protected route depends on get_current_tenant() + check_quota().
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.db import User, get_db

# Plan daily limits
PLAN_LIMITS: dict[str, int] = {
    "free": 5,
    "starter": 50,
    "pro": 999999,
}


# ─── Redis client (module-level singleton) ────────────────────────────────────

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class TenantContext(BaseModel):
    tenant_id: str
    email: str
    plan: str
    daily_limit: int


# ─── JWT helpers ──────────────────────────────────────────────────────────────

def create_access_token(tenant_id: str, email: str, plan: str) -> str:
    """Mint a JWT containing tenant_id (sub), email, plan."""
    payload = {
        "sub": tenant_id,
        "email": email,
        "plan": plan,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(
            (
                datetime.now(timezone.utc).timestamp()
                + settings.JWT_EXPIRE_MINUTES * 60
            )
        ),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── FastAPI dependencies ─────────────────────────────────────────────────────

async def get_current_tenant(
    authorization: Annotated[str, Header()],
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """
    Extracts Bearer token from Authorization header,
    decodes JWT, verifies user exists in DB, and returns TenantContext.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer '",
        )

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)

    tenant_id: str | None = payload.get("sub")
    email: str | None = payload.get("email")
    plan: str | None = payload.get("plan", "free")

    if not tenant_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims (sub, email)",
        )

    # Verify user exists in DB
    result = await db.execute(select(User).where(User.id == tenant_id, User.is_active == True))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    # Always use the plan from DB (source of truth for upgrades/downgrades)
    actual_plan = user.plan
    daily_limit = PLAN_LIMITS.get(actual_plan, PLAN_LIMITS["free"])

    return TenantContext(
        tenant_id=tenant_id,
        email=email,
        plan=actual_plan,
        daily_limit=daily_limit,
    )


async def check_quota(
    tenant: TenantContext = Depends(get_current_tenant),
    redis: aioredis.Redis = Depends(get_redis),
) -> TenantContext:
    """
    Reads Redis key usage:{tenant_id}:{date}.
    Raises 429 if over daily limit.
    Returns TenantContext so route handlers can access it.
    """
    today = date.today().isoformat()
    key = f"usage:{tenant.tenant_id}:{today}"

    used_raw = await redis.get(key)
    used = int(used_raw) if used_raw else 0

    if used >= tenant.daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily quota exceeded ({used}/{tenant.daily_limit}). "
                f"Upgrade your plan at /billing."
            ),
        )

    return tenant


async def increment_usage(tenant_id: str, redis: aioredis.Redis) -> int:
    """Increments daily usage counter. Returns new count."""
    today = date.today().isoformat()
    key = f"usage:{tenant_id}:{today}"
    count = await redis.incr(key)
    # Set TTL of 25 hours to ensure it expires the next day
    await redis.expire(key, 90000)
    return count


async def get_usage(tenant_id: str, redis: aioredis.Redis) -> dict:
    """Returns current usage data for a tenant."""
    today = date.today().isoformat()
    key = f"usage:{tenant_id}:{today}"
    used_raw = await redis.get(key)
    used = int(used_raw) if used_raw else 0
    return {"used": used, "date": today}
