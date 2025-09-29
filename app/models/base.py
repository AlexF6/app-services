from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

class AuditMixin:
    creado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    actualizado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
