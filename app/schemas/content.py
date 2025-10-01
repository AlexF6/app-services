# app/schemas/content.py
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.auditmixin import ContentType
from app.schemas.base import AuditOut


# ---------- Base ----------
class ContentBase(BaseModel):
    title: str = Field(..., max_length=200, description="Título de la obra (serie/película/documental)")
    type: ContentType = Field(..., description="Tipo de contenido (MOVIE, SERIES, DOCUMENTARY, etc.)")
    description: Optional[str] = Field(None, description="Descripción opcional")
    release_year: Optional[int] = Field(
        None, ge=1800, le=2100, description="Año de lanzamiento"
    )
    duration_minutes: Optional[int] = Field(
        None, ge=1, description="Duración total en minutos (para películas o capítulos)"
    )
    age_rating: Optional[str] = Field(
        None, max_length=10, description="Clasificación de edad (por ej. PG-13, TV-MA)"
    )
    genres: Optional[str] = Field(
        None,
        description="Géneros separados por coma (ej. Drama, Acción, Fantasía)",
    )


# ---------- Create ----------
class ContentCreate(ContentBase):
    """
    Crear un contenido. `title` y `type` son requeridos.
    """


# ---------- Update ----------
class ContentUpdate(BaseModel):
    """
    Actualización parcial de un contenido.
    """
    title: Optional[str] = Field(None, max_length=200)
    type: Optional[ContentType] = None
    description: Optional[str] = None
    release_year: Optional[int] = Field(None, ge=1800, le=2100)
    duration_minutes: Optional[int] = Field(None, ge=1)
    age_rating: Optional[str] = Field(None, max_length=10)
    genres: Optional[str] = None


# ---------- Output ----------
class ContentOut(ContentBase, AuditOut):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


# ---------- List item simplificado ----------
class ContentListItem(BaseModel):
    id: UUID
    title: str
    type: ContentType
    release_year: Optional[int] = None
    age_rating: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
