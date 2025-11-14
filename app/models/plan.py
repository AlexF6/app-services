# app/models/plan.py
import uuid
from sqlalchemy import Column, String, text, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.auditmixin import AuditMixin


class Plan(AuditMixin, Base):
    __tablename__ = "plans"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(80), unique=True, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    max_profiles = Column(Integer, nullable=False, server_default=text("1"))
    max_devices = Column(Integer, nullable=False, server_default=text("1"))
    video_quality = Column(String(20), nullable=False, server_default=text("'HD'"))

    subscriptions = relationship(
        "Subscription",
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
