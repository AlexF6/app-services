import uuid
from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.models.base import AuditMixin

class User(AuditMixin, Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True,
                default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    name = Column(String(120), nullable=False)
    password = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    active = Column(Boolean, nullable=False, server_default=text("true"))

    is_admin = Column(Boolean, nullable=False, server_default=text("false"), index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
