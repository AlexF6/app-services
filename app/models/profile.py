from sqlalchemy import Column, String, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base
from app.models.auditmixin import AuditMixin


class Profile(AuditMixin, Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True,
                default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    avatar = Column(String(255), nullable=True)
    maturity_rating = Column(String(20), nullable=True)

    user = relationship(
        "User", back_populates="profiles", foreign_keys=[user_id], passive_deletes=True
    )

    playbacks = relationship(
        "Playback",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    watchlist_items = relationship(
        "Watchlist",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

