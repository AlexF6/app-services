from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.plan import PlanCreate, PlanUpdate, PlanOut, PlanListItem
from app.schemas.subscriptions import (
    SubscriptionListItem,
)

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.get("", response_model=List[PlanListItem])
def list_plans(
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
    q: Optional[str] = Query(None, description="Search by name (ilike)"),
    min_price: Optional[Decimal] = Query(None, ge=Decimal("0")),
    max_price: Optional[Decimal] = Query(None, ge=Decimal("0")),
    video_quality: Optional[str] = Query(None, description="Exact filter by quality"),
    order_by: str = Query("fecha_creacion", pattern="^(name|price|fecha_creacion)$"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[PlanListItem]:
    """
    Lists all plans with filtering, sorting, and pagination (admin only).
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
        "fecha_creacion": Plan.fecha_creacion,
    }[order_by]
    qset = qset.order_by(col.asc() if order_dir == "asc" else col.desc())

    return qset.limit(limit).offset(offset).all()


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
) -> Plan:
    """
    Retrieves a single plan by ID (admin only).

    Raises:
        HTTPException: 404 Not Found if plan does not exist.
    """
    entity = db.get(Plan, plan_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Plan not found")
    return entity


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    admin: "User" = Depends(require_admin),
) -> Plan:
    """
    Creates a new plan (admin only). Validates uniqueness by name.

    Raises:
        HTTPException: 409 Conflict if plan name already exists.
    """
    exists = (
        db.query(Plan).filter(func.lower(Plan.name) == payload.name.lower()).first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Plan name already exists")

    entity = Plan(
        name=payload.name,
        price=payload.price,
        max_profiles=payload.max_profiles,
        max_devices=payload.max_devices,
        video_quality=payload.video_quality,
        creado_por=admin.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: UUID,
    payload: PlanUpdate,
    db: Session = Depends(get_db),
    admin: "User" = Depends(require_admin),
) -> Plan:
    """
    Updates a plan (admin only). Validates name uniqueness and field constraints.

    Raises:
        HTTPException: 404 Not Found if plan does not exist.
        HTTPException: 409 Conflict if the updated name already exists for another plan.
        HTTPException: 400 Bad Request if price, max_profiles, or max_devices are invalid.
    """
    entity = db.get(Plan, plan_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Plan not found")

    if payload.name is not None and payload.name != entity.name:
        conflict = (
            db.query(Plan)
            .filter(func.lower(Plan.name) == payload.name.lower(), Plan.id != entity.id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail="Plan name already exists")
        entity.name = payload.name

    if payload.price is not None:
        if payload.price <= 0:
            raise HTTPException(status_code=400, detail="price must be > 0")
        entity.price = payload.price
    if payload.max_profiles is not None:
        if payload.max_profiles < 1:
            raise HTTPException(status_code=400, detail="max_profiles must be >= 1")
        entity.max_profiles = payload.max_profiles
    if payload.max_devices is not None:
        if payload.max_devices < 1:
            raise HTTPException(status_code=400, detail="max_devices must be >= 1")
        entity.max_devices = payload.max_devices
    if payload.video_quality is not None:
        entity.video_quality = payload.video_quality

    entity.actualizado_por = admin.id
    db.commit()
    db.refresh(entity)
    return entity


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
) -> None:
    """
    Deletes a plan (admin only, hard delete). Fails with 409 Conflict if existing subscriptions reference it.

    Raises:
        HTTPException: 409 Conflict if the plan is referenced by existing subscriptions.
    """
    entity = db.get(Plan, plan_id)
    if not entity:
        return None

    try:
        db.delete(entity)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete plan with existing subscriptions",
        )
    return None


@router.get("/{plan_id}/subscriptions", response_model=List[SubscriptionListItem])
def list_plan_subscriptions(
    plan_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[SubscriptionListItem]:
    """
    Lists subscriptions associated with a specific plan (admin only).

    Raises:
        HTTPException: 404 Not Found if plan does not exist.
    """
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    q = db.query(Subscription).filter(Subscription.plan_id == plan_id)
    q = q.order_by(Subscription.fecha_creacion.desc())
    return q.limit(limit).offset(offset).all()
