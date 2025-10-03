import uuid
from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.auditmixin import AuditMixin


class User(AuditMixin, Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(120), nullable=False)
    password = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    active = Column(Boolean, nullable=False, server_default=text("true"))

    is_admin = Column(Boolean, nullable=False, server_default=text("false"), index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    profiles = relationship(
        "Profile",
        back_populates="user",
        foreign_keys="Profile.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    subscriptions = relationship(
        "Subscription",
        back_populates="user",
        foreign_keys="Subscription.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    payments = relationship(
        "Payment",
        back_populates="user",
        foreign_keys="Payment.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
