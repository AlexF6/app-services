# app/api/v1/me_plans.py
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.plan import Plan
from app.schemas.plan import PlanOut, PlanListItem

router = APIRouter(prefix="/me/plans", tags=["Plans (Me)"])


@router.get("", response_model=List[PlanListItem])
def list_available_plans(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),  # ensure authenticated access
    q: Optional[str] = Query(None, description="Search by name (ilike)"),
    min_price: Optional[Decimal] = Query(None, ge=Decimal("0")),
    max_price: Optional[Decimal] = Query(None, ge=Decimal("0")),
    video_quality: Optional[str] = Query(None, description="Exact filter by quality"),
    order_by: str = Query("created_at", pattern="^(name|price|created_at)$"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[PlanListItem]:
    """
    Lists available plans for the authenticated user (read-only).

    Same filters/sorting as admin list, but without admin privileges.
    """
    qset = db.query(Plan)

    if q:
        qset = qset.filter(func.lower(Plan.name).ilike(f"%{q.lower()}%"))
    if min_price is not None:
        qset = qset.filter(Plan.price >= min_price)
    if max_price is not None:
        qset = qset.filter(Plan.price <= max_price)
    if video_quality:
        qset = qset.filter(Plan.video_quality == video_quality)

    col = {
        "name": Plan.name,
        "price": Plan.price,
        "created_at": Plan.created_at,
    }[order_by]
    qset = qset.order_by(col.asc() if order_dir == "asc" else col.desc())

    return qset.limit(limit).offset(offset).all()


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan_details(
    plan_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PlanOut:
    """
    Retrieves details of a specific plan for the authenticated user (read-only).
    """
    entity = db.get(Plan, plan_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Plan not found")
    return entity
