# app/api/v1/me_payments.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.subscription import Subscription
from app.models.user import User
from app.models.payment import Payment
from app.models.auditmixin import PaymentStatus
from app.schemas.payment import PaymentOut, PaymentListItem
from pydantic import BaseModel


router = APIRouter(prefix="/me/payments", tags=["Payments (Me)"])


class PaginatedPayments(BaseModel):
    payments: List[PaymentListItem]
    total: int
    has_more: bool


@router.get("", response_model=PaginatedPayments)
def list_my_payments(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    # Useful filters for the user:
    subscription_id: Optional[UUID] = Query(None),
    status_q: Optional[PaymentStatus] = Query(None),
    provider: Optional[str] = Query(None, description="Contains filter (ilike)"),
    external_id: Optional[str] = Query(None, description="Exact filter"),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
    paid_from: Optional[datetime] = Query(None),
    paid_to: Optional[datetime] = Query(None),
    amount_min: Optional[Decimal] = Query(None, ge=Decimal("0")),
    amount_max: Optional[Decimal] = Query(None, ge=Decimal("0")),
    # Pagination
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedPayments:
    q = db.query(Payment).filter(Payment.user_id == me.id).options(
            joinedload(Payment.subscription)  # Subscription relation
            .joinedload(Subscription.plan)    # If you have a Plan relation
        )

    if subscription_id:
        q = q.filter(Payment.subscription_id == subscription_id)
    if status_q:
        q = q.filter(Payment.status == status_q)
    if provider:
        q = q.filter(Payment.provider.ilike(f"%{provider}%"))
    if external_id:
        q = q.filter(Payment.external_id == external_id)

    if created_from:
        q = q.filter(Payment.created_at >= created_from)
    if created_to:
        q = q.filter(Payment.created_at <= created_to)

    if paid_from:
        q = q.filter(and_(Payment.paid_at.is_not(None), Payment.paid_at >= paid_from))
    if paid_to:
        q = q.filter(and_(Payment.paid_at.is_not(None), Payment.paid_at <= paid_to))

    if amount_min is not None:
        q = q.filter(Payment.amount >= amount_min)
    if amount_max is not None:
        q = q.filter(Payment.amount <= amount_max)

    total = q.count()
    rows = (
        q.order_by(Payment.created_at.desc())
         .limit(limit)
         .offset(offset)
         .all()
    )
    def to_item(p: Payment) -> PaymentListItem:
      sub = getattr(p, "subscription", None)
      plan = getattr(sub, "plan", None)
      # Prefer plan.name if present; fall back to subscription.name if you keep one
      sub_name = getattr(plan, "name", None) or getattr(sub, "name", None)
      return PaymentListItem(
          id=p.id,
          user_id=p.user_id,
          subscription_id=p.subscription_id,
          amount=p.amount,
          currency=p.currency,
          status=p.status,
          paid_at=p.paid_at,
          provider=p.provider,
          external_id=p.external_id,
          subscription_name=sub_name,
          plan_name=getattr(plan, "name", None),
      )
    items = [to_item(p) for p in rows]

    return PaginatedPayments(payments=items, total=total, has_more=(offset + len(items) < total))


@router.get("/{payment_id}", response_model=PaymentOut)
def get_my_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Payment:
    entity = db.get(Payment, payment_id)
    if not entity or entity.user_id != me.id:
        # Don’t leak existence across users
        raise HTTPException(status_code=404, detail="Payment not found")
    return entity
