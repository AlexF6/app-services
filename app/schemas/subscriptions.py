from datetime import date, datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.auditmixin import SubscriptionStatus
from app.schemas.base import AuditOut


class SubscriptionBase(BaseModel):
    """Base schema for subscription data, containing core fields."""

    user_id: UUID = Field(..., description="Owner user UUID")
    plan_id: UUID = Field(..., description="Plan UUID")
    status: SubscriptionStatus = Field(
        default=SubscriptionStatus.ACTIVE, description="Subscription status"
    )
    start_date: Optional[date] = Field(
        default=None, description="If omitted, DB uses CURRENT_DATE"
    )
    end_date: Optional[date] = None
    renews_at: Optional[date] = None


class SubscriptionCreate(SubscriptionBase):
    """
    Schema for creating a new subscription.

    'start_date' can be omitted to use the database's default value.
    """


class SubscriptionUpdate(BaseModel):
    """
    Schema for partial update of a subscription.

    Note: 'user_id' is typically not changed here. If your business logic allows it,
    you would need to add it to this schema.
    """

    plan_id: Optional[UUID] = None
    status: Optional[SubscriptionStatus] = None
    end_date: Optional[date] = None
    renews_at: Optional[date] = None
    canceled_at: Optional[datetime] = None


class SubscriptionOut(SubscriptionBase, AuditOut):
    """Schema for output (read) operations, including audit and primary key fields."""

    id: UUID
    canceled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionListItem(BaseModel):
    """A lighter variant of SubscriptionOut, typically used for lists or summaries."""

    id: UUID
    user_id: UUID
    plan_id: UUID
    status: SubscriptionStatus
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    renews_at: Optional[date] = None
    canceled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)