from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin
from app.api.v1.auth import get_current_user

from app.models.subscription import Subscription
from app.models.user import User
from app.models.plan import Plan
from app.models.payment import (
    Payment,
)
from app.models.auditmixin import SubscriptionStatus

from app.schemas.subscriptions import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionOut,
    SubscriptionListItem,
)
from app.schemas.payment import (
    PaymentOut,
)


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def _ensure_user_and_plan(db: Session, user_id: UUID, plan_id: UUID) -> None:
    """
    Checks if the given User and Plan IDs exist in the database.

    Raises:
        HTTPException: 404 Not Found if either User or Plan is missing.
    """
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if not db.get(Plan, plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")


def _set_canceled_fields(entity: Subscription, when: Optional[datetime] = None) -> None:
    """
    Sets the subscription status to CANCELED and updates the canceled_at timestamp
    if it's currently None.
    """
    if entity.status != SubscriptionStatus.CANCELED:
        entity.status = SubscriptionStatus.CANCELED
    if entity.canceled_at is None:
        entity.canceled_at = when or datetime.now(timezone.utc)


@router.get("", response_model=List[SubscriptionListItem])
def list_subscriptions(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    user_id: Optional[UUID] = Query(None),
    plan_id: Optional[UUID] = Query(None),
    status_q: Optional[SubscriptionStatus] = Query(
        None, description="Filter by status"
    ),
    active_only: bool = Query(False, description="Equivalent to status=ACTIVE if True"),
    start_from: Optional[date] = Query(None, description="start_date >= start_from"),
    start_to: Optional[date] = Query(None, description="start_date <= start_to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[SubscriptionListItem]:
    """
    Lists subscriptions with filters and pagination (admin only).
    """
    q = db.query(Subscription)

    if user_id:
        q = q.filter(Subscription.user_id == user_id)
    if plan_id:
        q = q.filter(Subscription.plan_id == plan_id)

    if active_only and status_q:
        q = q.filter(Subscription.status == SubscriptionStatus.ACTIVE)
    elif active_only:
        q = q.filter(Subscription.status == SubscriptionStatus.ACTIVE)
    elif status_q:
        q = q.filter(Subscription.status == status_q)

    if start_from:
        q = q.filter(Subscription.start_date >= start_from)
    if start_to:
        q = q.filter(Subscription.start_date <= start_to)

    q = q.order_by(Subscription.start_date.desc(), Subscription.fecha_creacion.desc())

    items = q.limit(limit).offset(offset).all()
    return items


@router.get("/me", response_model=List[SubscriptionListItem])
def my_subscriptions(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    status_q: Optional[SubscriptionStatus] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[SubscriptionListItem]:
    """
    Lists subscriptions belonging to the authenticated user.
    """
    q = db.query(Subscription).filter(Subscription.user_id == me.id)
    if status_q:
        q = q.filter(Subscription.status == status_q)
    q = q.order_by(Subscription.start_date.desc(), Subscription.fecha_creacion.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Subscription:
    """
    Retrieves a subscription by ID (admin only).

    Raises:
        HTTPException: 404 Not Found if subscription does not exist.
    """
    sub = db.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Subscription:
    """
    Creates a subscription (admin only). Validates user/plan existence and checks for existing active subscriptions.

    Raises:
        HTTPException: 404 Not Found if User or Plan is invalid.
        HTTPException: 409 Conflict if User already has an active subscription and the new one is also ACTIVE.
    """
    _ensure_user_and_plan(db, payload.user_id, payload.plan_id)

    already_active = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == payload.user_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .first()
    )
    if already_active and payload.status == SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=409,
            detail="User already has an active subscription",
        )

    sub = Subscription(
        user_id=payload.user_id,
        plan_id=payload.plan_id,
        status=payload.status or SubscriptionStatus.ACTIVE,
        start_date=payload.start_date,
        end_date=payload.end_date,
        renews_at=payload.renews_at,
        creado_por=admin.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.put("/{subscription_id}", response_model=SubscriptionOut)
def update_subscription(
    subscription_id: UUID,
    payload: SubscriptionUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Subscription:
    """
    Updates allowed fields of the subscription (plan/status/dates) (admin only).

    Raises:
        HTTPException: 404 Not Found if subscription or new Plan ID is invalid.
    """
    sub = db.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if payload.plan_id and payload.plan_id != sub.plan_id:
        if not db.get(Plan, payload.plan_id):
            raise HTTPException(status_code=404, detail="Plan not found")
        sub.plan_id = payload.plan_id

    if payload.status is not None:
        if payload.status == SubscriptionStatus.CANCELED:
            _set_canceled_fields(sub, None)
        else:
            if sub.canceled_at is not None:
                sub.canceled_at = None
        sub.status = payload.status

    if payload.end_date is not None:
        sub.end_date = payload.end_date
    if payload.renews_at is not None:
        sub.renews_at = payload.renews_at
    if payload.canceled_at is not None:
        sub.canceled_at = payload.canceled_at
        if sub.canceled_at and sub.status != SubscriptionStatus.CANCELED:
            sub.status = SubscriptionStatus.CANCELED

    sub.actualizado_por = admin.id
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/{subscription_id}/cancel", response_model=SubscriptionOut)
def cancel_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    effective_end: Optional[date] = Query(
        None,
        description="Optional: effective end date (e.g., end of billing cycle)",
    ),
) -> Subscription:
    """
    Cancels a subscription (status=CANCELED, canceled_at=now). Optionally sets `effective_end` as the `end_date` (admin only).

    Raises:
        HTTPException: 404 Not Found if subscription does not exist.
    """
    sub = db.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    _set_canceled_fields(sub, None)
    if effective_end is not None:
        sub.end_date = effective_end

    sub.actualizado_por = admin.id
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/{subscription_id}/reactivate", response_model=SubscriptionOut)
def reactivate_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    new_end_date: Optional[date] = Query(
        None, description="Optional: new end date (e.g., renewed cycle end)"
    ),
) -> Subscription:
    """
    Reactivates a canceled subscription (status=ACTIVE, canceled_at=None) (admin only).

    Raises:
        HTTPException: 404 Not Found if subscription does not exist.
    """
    sub = db.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub.status = SubscriptionStatus.ACTIVE
    sub.canceled_at = None
    if new_end_date is not None:
        sub.end_date = new_end_date

    sub.actualizado_por = admin.id
    db.commit()
    db.refresh(sub)
    return sub


@router.get("/{subscription_id}/payments", response_model=List[PaymentOut])
def list_subscription_payments(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[PaymentOut]:
    """
    Lists payments associated with a subscription (admin only).

    Raises:
        HTTPException: 404 Not Found if subscription does not exist.
    """
    sub = db.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    q = db.query(Payment).filter(Payment.subscription_id == subscription_id)
    q = q.order_by(Payment.fecha_creacion.desc())
    return q.limit(limit).offset(offset).all()
