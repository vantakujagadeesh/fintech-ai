"""
SQLAlchemy async models for FinSight AI.
Tables: users, reports, plans — all with tenant_id for RLS.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.core.config import settings


# ─── Engine ───────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ─── Base ─────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reports: Mapped[list[Report]] = relationship("Report", back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} plan={self.plan}>"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)

    # Agent outputs
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sentiment_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    forecast: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    forecast_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report id={self.id} company={self.company} tenant={self.tenant_id}>"


class Plan(Base):
    """Reference table for plan limits."""

    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    price_inr: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Plan name={self.name} limit={self.daily_limit}>"


# ─── Dependency ───────────────────────────────────────────────────────────────

async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables and seed plan data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Enable Row Level Security on reports table
        await conn.execute(
            text("ALTER TABLE reports ENABLE ROW LEVEL SECURITY")
        )

    # Seed plan rows
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(select(Plan))
        existing = {p.name for p in result.scalars().all()}

        seed_plans = [
            Plan(name="free", daily_limit=5, price_inr=0, description="5 queries/day, GPT-4o-mini"),
            Plan(name="starter", daily_limit=50, price_inr=499, description="50 queries/day, GPT-4o-mini"),
            Plan(name="pro", daily_limit=999999, price_inr=1999, description="Unlimited, LLaMA-3 forecast"),
        ]

        for plan in seed_plans:
            if plan.name not in existing:
                session.add(plan)

        await session.commit()
