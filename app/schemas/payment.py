from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.auditmixin import PaymentStatus
from app.schemas.base import AuditOut


class PaymentBase(BaseModel):
    """Base schema for payment data, containing all core payment transaction fields."""

    user_id: UUID = Field(..., description="UUID of the user who made the payment")
    subscription_id: UUID = Field(
        ..., description="UUID of the associated subscription"
    )
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = Field(
        "USD", min_length=3, max_length=3, description="ISO-4217 currency code"
    )
    status: PaymentStatus = Field(
        default=PaymentStatus.PENDING, description="Payment status"
    )
    provider: Optional[str] = Field(
        None, max_length=40, description="Payment provider (Stripe, PayPal, etc.)"
    )
    external_id: Optional[str] = Field(
        None, max_length=120, description="External transaction ID"
    )
    paid_at: Optional[datetime] = Field(
        None, description="Date/time when the successful payment was recorded"
    )


class PaymentCreate(PaymentBase):
    """
    Schema for creating a new payment record.

    'currency' (default USD) and 'status' (default PENDING) can be omitted on creation.
    """


class PaymentUpdate(BaseModel):
    """
    Schema for partial update of a payment record.
    """

    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[PaymentStatus] = None
    provider: Optional[str] = None
    external_id: Optional[str] = None
    paid_at: Optional[datetime] = None


class PaymentOut(PaymentBase, AuditOut):
    """Schema for output (read) operations, including audit and primary key fields."""

    id: UUID

    model_config = ConfigDict(from_attributes=True)


class PaymentListItem(BaseModel):
    """A simplified schema for payment data, typically used for lists or summaries."""

    id: UUID
    amount: Decimal
    currency: str
    status: PaymentStatus
    paid_at: Optional[datetime] = None
    provider: Optional[str] = None
    external_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
