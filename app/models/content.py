import uuid
from sqlalchemy import Column, String, Enum as SAEnum, text, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.auditmixin import AuditMixin, ContentType


class Content(AuditMixin, Base):
    __tablename__ = "contents"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    title = Column(String(200), nullable=False, index=True)
    type = Column(SAEnum(ContentType, name="content_type"), nullable=False)
    description = Column(Text, nullable=True)
    release_year = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # ← renamed
    age_rating = Column(String(10), nullable=True)
    genres = Column(Text, nullable=True)
    video_url = Column(Text, nullable=True)
    thumbnail = Column(Text, nullable=True)

    episodes = relationship(
        "Episode",
        back_populates="content",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    playbacks = relationship(
        "Playback",
        back_populates="content",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    watchlisted_by = relationship(
        "Watchlist",
        back_populates="content",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
