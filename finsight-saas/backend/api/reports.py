"""
GET /reports — Paginated report history from PostgreSQL.
Only returns reports belonging to the authenticated tenant.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import Report, get_db
from backend.core.tenancy import TenantContext, get_current_tenant

router = APIRouter()


class ReportSummary(BaseModel):
    id: str
    job_id: str
    company: str
    user_query: str
    risk_score: Optional[float]
    sentiment: Optional[str]
    forecast: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaginatedReportsResponse(BaseModel):
    items: list[ReportSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("/reports", response_model=PaginatedReportsResponse)
async def list_reports(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    company: Optional[str] = Query(default=None, description="Filter by company name"),
    forecast: Optional[str] = Query(default=None, description="Filter by forecast: buy|hold|sell"),
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> PaginatedReportsResponse:
    """
    Retrieve paginated report history for the current tenant.
    Filters by company and forecast are optional.
    """
    # Base query with tenant isolation
    base_query = select(Report).where(Report.tenant_id == tenant.tenant_id)

    # Optional filters
    if company:
        base_query = base_query.where(Report.company.ilike(f"%{company}%"))
    if forecast:
        base_query = base_query.where(Report.forecast == forecast)

    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Paginate and order
    offset = (page - 1) * page_size
    result = await db.execute(
        base_query.order_by(Report.created_at.desc()).offset(offset).limit(page_size)
    )
    reports = result.scalars().all()

    return PaginatedReportsResponse(
        items=[ReportSummary.model_validate(r) for r in reports],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/reports/{report_id}", response_model=ReportSummary)
async def get_report(
    report_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ReportSummary:
    """Retrieve a single report by ID. Tenant-scoped."""
    from fastapi import HTTPException, status

    result = await db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.tenant_id == tenant.tenant_id,
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )

    return ReportSummary.model_validate(report)
