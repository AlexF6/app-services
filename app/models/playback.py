# app/models/playback.py
import uuid
from sqlalchemy import (
    Column,
    String,
    text,
    DateTime,
    Integer,
    ForeignKey,
    Boolean,
    func,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.auditmixin import AuditMixin


class Playback(AuditMixin, Base):
    __tablename__ = "playbacks"

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
    episode_id = Column(
        UUID(as_uuid=True),
        ForeignKey("episodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    started_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at = Column(DateTime(timezone=True), nullable=True)
    progress_seconds = Column(Integer, nullable=False, server_default=text("0"))
    completed = Column(Boolean, nullable=False, server_default=text("false"))
    device = Column(String(200), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    profile = relationship(
        "Profile",
        back_populates="playbacks",
        foreign_keys=[profile_id],
        passive_deletes=True,
    )
    content = relationship(
        "Content",
        back_populates="playbacks",
        foreign_keys=[content_id],
        passive_deletes=True,
    )
    episode = relationship(
        "Episode",
        back_populates="playbacks",
        foreign_keys=[episode_id],
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_playbacks_profile_started", "profile_id", "started_at"),
        Index("ix_playbacks_content_episode", "content_id", "episode_id"),
        CheckConstraint("progress_seconds >= 0", name="ck_playbacks_progress_nonneg"),
        CheckConstraint("(duration_seconds IS NULL) OR (duration_seconds >= 0)",
                        name="ck_playbacks_duration_nonneg"),
        Index(
            'uq_active_playback',
            'profile_id', 'device', 'content_id', 'episode_id',
            unique=True,
            postgresql_where=text('completed = false')
        ),
    )