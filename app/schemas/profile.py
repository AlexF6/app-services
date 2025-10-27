from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import AuditOut


class ProfileBase(BaseModel):
    """Base schema for profile data, containing core configuration fields."""

    user_id: UUID = Field(..., description="UUID of the user who owns the profile")
    name: str = Field(..., min_length=1, max_length=60, description="Profile name")
    avatar: Optional[str] = Field(
        None, max_length=255, description="URL or path for the profile avatar"
    )
    maturity_rating: Optional[str] = Field(
        None,
        max_length=20,
        description="Maturity rating of the profile (e.g., G, PG-13, TV-MA)",
    )


class ProfileCreate(ProfileBase):
    """
    Create a new profile for a user.
    """

class ProfileCreateMe(BaseModel):
    """User-scoped create schema (no user_id in payload)."""
    name: str = Field(..., min_length=1, max_length=60)
    avatar: Optional[str] = Field(None, max_length=255)
    maturity_rating: Optional[str] = Field(None, max_length=20)


class ProfileUpdate(BaseModel):
    """
    Partial update of a profile.
    """

    name: Optional[str] = Field(None, max_length=60)
    avatar: Optional[str] = Field(None, max_length=255)
    maturity_rating: Optional[str] = Field(None, max_length=20)


class ProfileOut(ProfileBase, AuditOut):
    """Schema for output (read) operations, including audit and primary key fields."""

    id: UUID

    model_config = ConfigDict(from_attributes=True)


class ProfileListItem(BaseModel):
    """A simplified schema for profile data, typically used for lists or summaries."""

    id: UUID
    user_id: UUID
    name: str
    avatar: Optional[str] = None
    maturity_rating: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
