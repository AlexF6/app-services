import uuid
from sqlalchemy import (
    Column,
    String,
    Enum as SAEnum,
    DateTime,
    text,
    Numeric,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.auditmixin import AuditMixin, PaymentStatus


class Payment(AuditMixin, Base):
    __tablename__ = "payments"

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
    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, server_default=text("'USD'"))
    status = Column(
        SAEnum(PaymentStatus, name="payment_status"),
        nullable=False,
        server_default=text("'PENDING'"),
    )
    paid_at = Column(DateTime(timezone=True), nullable=True)
    provider = Column(String(40), nullable=True)
    external_id = Column(String(120), nullable=True)

    user = relationship("User", back_populates="payments", foreign_keys=[user_id])
    subscription = relationship(
        "Subscription", back_populates="payments", foreign_keys=[subscription_id]
    )
