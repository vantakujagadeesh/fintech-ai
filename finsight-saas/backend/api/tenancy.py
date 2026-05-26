# backend/core/tenancy.py
from fastapi import HTTPException, Depends, Header
from jose import jwt, JWTError
import redis
from datetime import date

SECRET = "your-jwt-secret"
r = redis.Redis(host="localhost", port=6379, db=0)

PLAN_LIMITS = {
    "free":    5,
    "starter": 50,
    "pro":     999999,
}

async def get_current_tenant(authorization: str = Header(...)) -> dict:
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        return {
            "tenant_id": payload["sub"],
            "plan":      payload.get("plan", "free"),
            "email":     payload.get("email")
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def check_quota(tenant: dict = Depends(get_current_tenant)) -> dict:
    key = f"usage:{tenant['tenant_id']}:{date.today()}"
    usage = int(r.get(key) or 0)
    limit = PLAN_LIMITS.get(tenant["plan"], 5)

    if usage >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit of {limit} queries reached. Upgrade your plan."
        )

    r.incr(key)
    r.expire(key, 86400)  # reset after 24h
    return tenant