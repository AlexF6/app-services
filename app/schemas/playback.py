# app/schemas/playback.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base import AuditOut


# ---------- Base ----------
class PlaybackBase(BaseModel):
    profile_id: UUID = Field(..., description="Perfil que realizó la reproducción")
    content_id: UUID = Field(..., description="Contenido reproducido")
    episode_id: Optional[UUID] = Field(
        None, description="Episodio reproducido (si aplica, en series)"
    )
    started_at: Optional[datetime] = Field(
        None, description="Fecha y hora de inicio de la reproducción"
    )
    ended_at: Optional[datetime] = Field(
        None, description="Fecha y hora de finalización de la reproducción"
    )
    progress_seconds: Optional[int] = Field(
        0, ge=0, description="Segundos reproducidos hasta el momento"
    )
    completed: Optional[bool] = Field(
        False, description="True si el contenido se terminó de ver"
    )
    device: Optional[str] = Field(
        None, max_length=80, description="Dispositivo desde el cual se reproduce"
    )


# ---------- Create ----------
class PlaybackCreate(PlaybackBase):
    """
    Crear un nuevo registro de reproducción.
    - Si `started_at` no se envía, se usará la fecha actual.
    """


# ---------- Update ----------
class PlaybackUpdate(BaseModel):
    """
    Actualizar parcialmente un registro de reproducción.
    """
    ended_at: Optional[datetime] = None
    progress_seconds: Optional[int] = Field(None, ge=0)
    completed: Optional[bool] = None
    device: Optional[str] = Field(None, max_length=80)


# ---------- Output ----------
class PlaybackOut(PlaybackBase, AuditOut):
    id: UUID
    started_at: datetime  # aseguramos que viene seteado
    # ended_at y otros ya vienen del base

    model_config = ConfigDict(from_attributes=True)


# ---------- List item simplificado ----------
class PlaybackListItem(BaseModel):
    id: UUID
    profile_id: UUID
    content_id: UUID
    episode_id: Optional[UUID]
    started_at: datetime
    ended_at: Optional[datetime]
    progress_seconds: int
    completed: bool
    device: Optional[str]

    model_config = ConfigDict(from_attributes=True)
