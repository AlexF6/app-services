# app/api/v1/me_subscriptions.py
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.auth import get_current_user

from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.auditmixin import SubscriptionStatus

from app.schemas.subscriptions import (
    SubscriptionCreateMe,
    SubscriptionOut,
    SubscriptionListItem,
)
from app.schemas.payment import PaymentOut

router = APIRouter(prefix="/me/subscriptions", tags=["Subscriptions (Me)"])


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _get_owned_subscription(db: Session, owner_id: UUID, sub_id: UUID) -> Subscription:
    sub = db.get(Subscription, sub_id)
    # Return 404 instead of 403 to avoid leaking existence
    if not sub or sub.user_id != owner_id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


def _plan_exists(db: Session, plan_id: UUID) -> None:
    if not db.get(Plan, plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")


def _set_canceled_fields(entity: Subscription, when: Optional[datetime] = None) -> None:
    if entity.status != SubscriptionStatus.CANCELED:
        entity.status = SubscriptionStatus.CANCELED
    if entity.canceled_at is None:
        entity.canceled_at = when or datetime.now(timezone.utc)


# Small input model for the switch-plan action
class SwitchPlanIn(BaseModel):
    plan_id: UUID
    effective_end: Optional[date] = None  # e.g., end of current cycle before switch


# ---------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------
@router.get("", response_model=List[SubscriptionListItem])
def list_my_subscriptions(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    status_q: Optional[SubscriptionStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[SubscriptionListItem]:
    """
    Lists subscriptions belonging to the authenticated user.
    """
    q = db.query(Subscription).filter(Subscription.user_id == me.id)
    if status_q:
        q = q.filter(Subscription.status == status_q)
    q = q.order_by(Subscription.start_date.desc(), Subscription.created_at.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/current", response_model=SubscriptionOut)
def get_my_current_subscription(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> SubscriptionOut:
    """
    Returns the most recent ACTIVE subscription for the user.
    """
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == me.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(Subscription.start_date.desc(), Subscription.created_at.desc())
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription")
    return sub


@router.get("/{subscription_id}", response_model=SubscriptionOut)
def get_my_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> SubscriptionOut:
    """
    Get one of my subscriptions by ID (404 if not mine).
    """
    sub = _get_owned_subscription(db, me.id, subscription_id)
    return sub


# ---------------------------------------------------------------------
# Create (self-service)
# ---------------------------------------------------------------------
@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_my_subscription(
    payload: SubscriptionCreateMe,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> SubscriptionOut:
    """
    Create a subscription for the authenticated user.

    Guards:
    - Validates plan exists.
    - Prevents creating a second ACTIVE subscription.
    """
    _plan_exists(db, payload.plan_id)

    already_active = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == me.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .first()
    )
    if already_active:
        raise HTTPException(
            status_code=409, detail="You already have an active subscription"
        )

    sub = Subscription(
        user_id=me.id,
        plan_id=payload.plan_id,
        status=SubscriptionStatus.ACTIVE,
        start_date=payload.start_date,  # DB default if None
        end_date=payload.end_date,
        renews_at=payload.renews_at,
        created_by=me.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# ---------------------------------------------------------------------
# Switch plan (self-service, guarded)
# ---------------------------------------------------------------------
@router.post("/{subscription_id}/switch-plan", response_model=SubscriptionOut)
def switch_my_subscription_plan(
    subscription_id: UUID,
    body: SwitchPlanIn,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> SubscriptionOut:
    """
    Switch the plan for my ACTIVE subscription.

    Behavior:
    - Requires the subscription to belong to me and be ACTIVE.
    - New plan must exist.
    - Optionally sets an effective end date of current cycle before switching.
      (If provided, sets `end_date`; you can pair this with a new subscription creation
       flow in the UI, or treat it as an immediate switch by leaving it null.)
    """
    sub = _get_owned_subscription(db, me.id, subscription_id)
    if sub.status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=409, detail="Only ACTIVE subscriptions can switch plan"
        )

    _plan_exists(db, body.plan_id)

    # If plan is the same, make it idempotent
    if body.plan_id == sub.plan_id and body.effective_end is None:
        return sub

    if body.effective_end is not None:
        sub.end_date = body.effective_end

    sub.plan_id = body.plan_id
    sub.updated_by = me.id

    db.commit()
    db.refresh(sub)
    return sub


# ---------------------------------------------------------------------
# Cancel / Reactivate (self-service)
# ---------------------------------------------------------------------
@router.post("/{subscription_id}/cancel", response_model=SubscriptionOut)
def cancel_my_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    effective_end: Optional[date] = Query(
        None, description="Optional: effective end date (e.g., end of current cycle)"
    ),
) -> SubscriptionOut:
    """
    Cancel my subscription. Sets status=CANCELED and canceled_at=now.
    Optionally sets `end_date` to `effective_end`.
    """
    sub = _get_owned_subscription(db, me.id, subscription_id)

    _set_canceled_fields(sub, None)
    if effective_end is not None:
        sub.end_date = effective_end

    sub.updated_by = me.id
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/{subscription_id}/reactivate", response_model=SubscriptionOut)
def reactivate_my_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    new_end_date: Optional[date] = Query(
        None, description="Optional: new end date (e.g., renewed cycle end)"
    ),
) -> SubscriptionOut:
    """
    Reactivate my subscription (sets status=ACTIVE and clears canceled_at).
    """
    sub = _get_owned_subscription(db, me.id, subscription_id)

    sub.status = SubscriptionStatus.ACTIVE
    sub.canceled_at = None
    if new_end_date is not None:
        sub.end_date = new_end_date

    sub.updated_by = me.id
    db.commit()
    db.refresh(sub)
    return sub


# ---------------------------------------------------------------------
# Payments (owner-scoped)
# ---------------------------------------------------------------------
@router.get("/{subscription_id}/payments", response_model=List[PaymentOut])
def list_my_subscription_payments(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[PaymentOut]:
    """
    List payments for one of my subscriptions.
    """
    _ = _get_owned_subscription(db, me.id, subscription_id)

    q = db.query(Payment).filter(Payment.subscription_id == subscription_id)
    q = q.order_by(Payment.created_at.desc())
    return q.limit(limit).offset(offset).all()
