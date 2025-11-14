from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from enum import Enum as PyEnum


class AuditMixin:
    """Mixin class to add audit fields to SQLAlchemy models."""

    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    updated_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class ContentType(PyEnum):
    """Enumeration for the types of content available."""

    MOVIE = "MOVIE"
    SERIES = "SERIES"
    VIDEOS = "VIDEOS"


class SubscriptionStatus(PyEnum):
    """Enumeration for the possible states of a user subscription."""

    ACTIVE = "ACTIVE"
    CANCELED = "CANCELED"
    PAST_DUE = "PAST_DUE"


class PaymentStatus(PyEnum):
    """Enumeration for the possible states of a payment transaction."""

    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
