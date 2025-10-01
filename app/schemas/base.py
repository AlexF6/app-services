from pydantic import BaseModel
import uuid
from datetime import datetime
from typing import Optional


class AuditOut(BaseModel):
    """
    Schema for outputting audit fields (creation and update metadata).
    """

    created_by: uuid.UUID
    updated_by: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
