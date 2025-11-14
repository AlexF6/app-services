from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base import AuditOut

class ProfileBase(BaseModel):
    user_id: UUID = Field(..., description="UUID of the user who owns the profile")
    name: str = Field(..., min_length=1, max_length=60, description="Profile name")
    avatar: Optional[str] = Field(None, max_length=255, description="URL or path for the profile avatar")
    maturity_rating: Optional[str] = Field(None, max_length=20, description="Maturity rating (e.g., G, PG-13, TV-MA)")

class ProfileCreate(ProfileBase):
    """Admin-scoped create (includes user_id)."""

class ProfileCreateMe(BaseModel):
    """User-scoped create (no user_id in payload)."""
    name: str = Field(..., min_length=1, max_length=60)
    avatar: Optional[str] = Field(None, max_length=255)
    maturity_rating: Optional[str] = Field(None, max_length=20)

class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=60)
    avatar: Optional[str] = Field(None, max_length=255)
    maturity_rating: Optional[str] = Field(None, max_length=20)

class ProfileOut(ProfileBase, AuditOut):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class ProfileListItem(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    avatar: Optional[str] = None
    maturity_rating: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
