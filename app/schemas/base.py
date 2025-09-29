from pydantic import BaseModel
import uuid
from datetime import datetime
from typing import Optional

class AuditOut(BaseModel):
    creado_por: uuid.UUID
    actualizado_por: Optional[uuid.UUID] = None
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True
