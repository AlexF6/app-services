import uuid
from sqlalchemy import Column, String, Text, text, Integer, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.auditmixin import AuditMixin


class Episode(AuditMixin, Base):
    __tablename__ = "episodes"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    content_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    season_number = Column(Integer, nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    release_date = Column(Date, nullable=True)
    video_url = Column(Text, nullable=True)

    content = relationship(
        "Content",
        back_populates="episodes",
        foreign_keys=[content_id],
        passive_deletes=True,
    )

    playbacks = relationship(
        "Playback",
        back_populates="episode",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
