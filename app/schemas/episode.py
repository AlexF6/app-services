# app/schemas/episode.py
from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base import AuditOut


# ---------- Base ----------
class EpisodeBase(BaseModel):
    content_id: UUID = Field(..., description="UUID del contenido al que pertenece el episodio")
    season_number: int = Field(..., ge=1, description="Número de la temporada (>=1)")
    episode_number: int = Field(..., ge=1, description="Número del episodio (>=1)")
    title: str = Field(..., max_length=200, description="Título del episodio")
    duration_minutes: Optional[int] = Field(
        None, ge=1, description="Duración del episodio en minutos"
    )
    release_date: Optional[date] = Field(
        None, description="Fecha de lanzamiento del episodio"
    )


# ---------- Create ----------
class EpisodeCreate(EpisodeBase):
    """
    Crear un nuevo episodio asociado a un contenido existente.
    """


# ---------- Update ----------
class EpisodeUpdate(BaseModel):
    """
    Actualizar parcialmente un episodio.
    """
    season_number: Optional[int] = Field(None, ge=1)
    episode_number: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, max_length=200)
    duration_minutes: Optional[int] = Field(None, ge=1)
    release_date: Optional[date] = None


# ---------- Output ----------
class EpisodeOut(EpisodeBase, AuditOut):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


# ---------- List item simplificado ----------
class EpisodeListItem(BaseModel):
    id: UUID
    content_id: UUID
    season_number: int
    episode_number: int
    title: str
    duration_minutes: Optional[int] = None
    release_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)
