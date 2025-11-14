# app/models/subscription.py
import uuid
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    text,
    Enum as SAEnum,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.auditmixin import AuditMixin, SubscriptionStatus


class Subscription(AuditMixin, Base):
    __tablename__ = "subscriptions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status = Column(
        SAEnum(SubscriptionStatus, name="subscription_status", create_type=False),
        nullable=False,
        server_default=text("'ACTIVE'::subscription_status"),
    )

    start_date = Column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    end_date = Column(Date, nullable=True)
    renews_at = Column(Date, nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship(
        "User",
        back_populates="subscriptions",
        foreign_keys=[user_id],
        passive_deletes=True,
    )

    plan = relationship(
        "Plan",
        back_populates="subscriptions",
        foreign_keys=[plan_id],
        passive_deletes=True,
    )

    payments = relationship(
        "Payment",
        back_populates="subscription",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
