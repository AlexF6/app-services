# app/api/v1/me_subscriptions.py
from datetime import date
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.subscription import Subscription
from app.models.plan import Plan
from app.models.auditmixin import SubscriptionStatus
from app.schemas.subscriptions import (
    SubscriptionCreateMe, SubscriptionUpdate, SubscriptionOut, SubscriptionListItem
)
from app.models.payment import Payment
from app.schemas.payment import PaymentOut

router = APIRouter(prefix="/me/subscriptions", tags=["Subscriptions (Me)"])

def _ensure_owner(db: Session, me: User, sub_id: UUID) -> Subscription:
    sub = db.get(Subscription, sub_id)
    if not sub or sub.user_id != me.id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub

@router.get("", response_model=List[SubscriptionListItem])
def list_my_subscriptions(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    status_q: Optional[SubscriptionStatus] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    q = db.query(Subscription).filter(Subscription.user_id == me.id)
    if status_q:
        q = q.filter(Subscription.status == status_q)
    q = q.order_by(Subscription.start_date.desc(), Subscription.created_at.desc())
    return q.limit(limit).offset(offset).all()

@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_my_subscription(
    payload: SubscriptionCreateMe,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    if not db.get(Plan, payload.plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")

    already_active = (
        db.query(Subscription)
        .filter(Subscription.user_id == me.id, Subscription.status == SubscriptionStatus.ACTIVE)
        .first()
    )
    if already_active:
        raise HTTPException(status_code=409, detail="User already has an active subscription")

    sub = Subscription(
        user_id=me.id,
        plan_id=payload.plan_id,
        status=SubscriptionStatus.ACTIVE,
        start_date=payload.start_date,
        end_date=payload.end_date,
        renews_at=payload.renews_at,
        created_by=me.id,
    )
    db.add(sub); db.commit(); db.refresh(sub)
    return sub

@router.post("/{subscription_id}/cancel", response_model=SubscriptionOut)
def cancel_my_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    effective_end: Optional[date] = Query(None),
):
    sub = _ensure_owner(db, me, subscription_id)
    sub.status = SubscriptionStatus.CANCELED
    if effective_end is not None:
        sub.end_date = effective_end
    sub.updated_by = me.id
    db.commit(); db.refresh(sub)
    return sub

@router.post("/{subscription_id}/reactivate", response_model=SubscriptionOut)
def reactivate_my_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    new_end_date: Optional[date] = Query(None),
):
    sub = _ensure_owner(db, me, subscription_id)
    sub.status = SubscriptionStatus.ACTIVE
    sub.canceled_at = None
    if new_end_date is not None:
        sub.end_date = new_end_date
    sub.updated_by = me.id
    db.commit(); db.refresh(sub)
    return sub

@router.get("/{subscription_id}/payments", response_model=List[PaymentOut])
def list_my_subscription_payments(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    _ = _ensure_owner(db, me, subscription_id)
    q = db.query(Payment).filter(Payment.subscription_id == subscription_id)
    q = q.order_by(Payment.created_at.desc())
    return q.limit(limit).offset(offset).all()
