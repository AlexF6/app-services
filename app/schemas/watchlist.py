# app/schemas/watchlist.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base import AuditOut


# ---------- Base ----------
class WatchlistBase(BaseModel):
    profile_id: UUID = Field(..., description="UUID del perfil que agregó el contenido a la lista")
    content_id: UUID = Field(..., description="UUID del contenido agregado a la lista")


# ---------- Create ----------
class WatchlistCreate(WatchlistBase):
    """
    Crear un ítem de watchlist. `added_at` lo pone el servidor (default now()).
    """


# ---------- Update ----------
class WatchlistUpdate(BaseModel):
    """
    Permite cambiar sólo el contenido o perfil si tu negocio lo permite (normalmente no se cambia).
    """
    profile_id: Optional[UUID] = None
    content_id: Optional[UUID] = None


# ---------- Output ----------
class WatchlistOut(WatchlistBase, AuditOut):
    id: UUID
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Lista simplificada ----------
class WatchlistListItem(BaseModel):
    id: UUID
    profile_id: UUID
    content_id: UUID
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)
