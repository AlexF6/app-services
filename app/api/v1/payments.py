from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin
from app.api.v1.auth import get_current_user

from app.models.payment import Payment
from app.models.user import User
from app.models.subscription import Subscription
from app.models.auditmixin import PaymentStatus

from app.schemas.payment import (
    PaymentCreate,
    PaymentUpdate,
    PaymentOut,
    PaymentListItem,
)

router = APIRouter(prefix="/payments", tags=["Payments"])


def _ensure_user_and_subscription(
    db: Session, user_id: UUID, subscription_id: UUID
) -> None:
    """
    Checks for the existence and ownership consistency of the User and Subscription.

    Raises:
        HTTPException: 404 Not Found if User or Subscription doesn't exist.
        HTTPException: 409 Conflict if subscription_id does not belong to the provided user_id.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub = db.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if sub.user_id != user_id:
        raise HTTPException(
            status_code=409,
            detail="subscription_id does not belong to the provided user_id",
        )


def _auto_manage_paid_at(
    entity: Payment,
    new_status: Optional[PaymentStatus],
    incoming_paid_at: Optional[datetime],
) -> None:
    """
    Automatically manages the 'paid_at' timestamp based on status change:
      - If status changes to PAID and 'paid_at' is missing, it sets it to now().
      - If 'paid_at' is explicitly provided, it is always respected.
    """
    if new_status is None:
        if incoming_paid_at is not None:
            entity.paid_at = incoming_paid_at
        return

    if new_status == PaymentStatus.PAID:
        entity.status = PaymentStatus.PAID
        entity.paid_at = incoming_paid_at or datetime.now(timezone.utc)
    else:
        entity.status = new_status
        if incoming_paid_at is not None:
            entity.paid_at = incoming_paid_at


@router.get("", response_model=List[PaymentListItem])
def list_payments(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    user_id: Optional[UUID] = Query(None),
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
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[PaymentListItem]:
    """
    Lists payments with filters and pagination (admin only).
    """
    q = db.query(Payment)

    if user_id:
        q = q.filter(Payment.user_id == user_id)
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
        q = q.filter(Payment.paid_at.is_not(None), Payment.paid_at >= paid_from)
    if paid_to:
        q = q.filter(Payment.paid_at.is_not(None), Payment.paid_at <= paid_to)

    if amount_min is not None:
        q = q.filter(Payment.amount >= amount_min)
    if amount_max is not None:
        q = q.filter(Payment.amount <= amount_max)

    q = q.order_by(Payment.created_at.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/me", response_model=List[PaymentListItem])
def my_payments(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    status_q: Optional[PaymentStatus] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[PaymentListItem]:
    """
    Lists payments belonging to the authenticated user.
    """
    q = db.query(Payment).filter(Payment.user_id == me.id)
    if status_q:
        q = q.filter(Payment.status == status_q)

    q = q.order_by(Payment.created_at.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Payment:
    """
    Retrieves a payment by ID (admin only).

    Raises:
        HTTPException: 404 Not Found if payment does not exist.
    """
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Payment:
    """
    Creates a new payment (admin only). Validates user/subscription consistency and manages status/paid_at fields.

    Raises:
        HTTPException: 404 Not Found if User or Subscription doesn't exist.
        HTTPException: 409 Conflict if subscription_id does not belong to the provided user_id.
    """
    _ensure_user_and_subscription(db, payload.user_id, payload.subscription_id)

    entity = Payment(
        user_id=payload.user_id,
        subscription_id=payload.subscription_id,
        amount=payload.amount,
        currency=payload.currency or "USD",
        provider=payload.provider,
        external_id=payload.external_id,
        status=payload.status or PaymentStatus.PENDING,
        created_by=admin.id,
    )

    _auto_manage_paid_at(entity, entity.status, payload.paid_at)

    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/{payment_id}", response_model=PaymentOut)
def update_payment(
    payment_id: UUID,
    payload: PaymentUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Payment:
    """
    Updates allowed fields of the payment (admin only). Manages currency format and status/paid_at rules.

    Raises:
        HTTPException: 404 Not Found if payment does not exist.
        HTTPException: 400 Bad Request if amount is not positive or currency is invalid.
    """
    entity = db.get(Payment, payment_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payload.amount is not None:
        if payload.amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be > 0")
        entity.amount = payload.amount
    if payload.currency is not None:
        if len(payload.currency) != 3:
            raise HTTPException(
                status_code=400, detail="currency must be 3-letter ISO code"
            )
        entity.currency = payload.currency.upper()

    if payload.provider is not None:
        entity.provider = payload.provider or None
    if payload.external_id is not None:
        entity.external_id = payload.external_id or None

    _auto_manage_paid_at(entity, payload.status, payload.paid_at)

    entity.updated_by = admin.id
    db.commit()
    db.refresh(entity)
    return entity


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    """
    Deletes a payment (hard delete, admin only).
    """
    entity = db.get(Payment, payment_id)
    if not entity:
        return None
    db.delete(entity)
    db.commit()
    return None
