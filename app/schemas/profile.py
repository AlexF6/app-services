# app/schemas/profile.py
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import AuditOut


# ---------- Base ----------
class ProfileBase(BaseModel):
    user_id: UUID = Field(..., description="UUID del usuario dueño del perfil")
    name: str = Field(..., min_length=1, max_length=60, description="Nombre del perfil")
    avatar: Optional[str] = Field(
        None,
        max_length=255,
        description="URL o ruta de avatar para el perfil"
    )
    maturity_rating: Optional[str] = Field(
        None,
        max_length=20,
        description="Clasificación de madurez del perfil (ej. G, PG-13, TV-MA)"
    )


# ---------- Create ----------
class ProfileCreate(ProfileBase):
    """
    Crear un nuevo perfil para un usuario.
    """


# ---------- Update ----------
class ProfileUpdate(BaseModel):
    """
    Actualización parcial de un perfil.
    """
    name: Optional[str] = Field(None, max_length=60)
    avatar: Optional[str] = Field(None, max_length=255)
    maturity_rating: Optional[str] = Field(None, max_length=20)


# ---------- Output ----------
class ProfileOut(ProfileBase, AuditOut):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


# ---------- List item simplificado ----------
class ProfileListItem(BaseModel):
    id: UUID
    name: str
    avatar: Optional[str] = None
    maturity_rating: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
