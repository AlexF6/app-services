# app/models/watchlist.py
import uuid
from sqlalchemy import Column, DateTime, Index, UniqueConstraint, text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.auditmixin import AuditMixin


class Watchlist(AuditMixin, Base):
    __tablename__ = "watchlists"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    added_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile = relationship(
        "Profile",
        back_populates="watchlist_items",
        foreign_keys=[profile_id],
        passive_deletes=True,
    )
    content = relationship(
        "Content",
        back_populates="watchlisted_by",
        foreign_keys=[content_id],
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("profile_id", "content_id", name="uq_watchlists_profile_content"),
        Index("ix_watchlists_profile_content", "profile_id", "content_id"),
    )