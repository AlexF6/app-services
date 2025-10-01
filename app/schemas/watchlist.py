from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base import AuditOut


class WatchlistBase(BaseModel):
    """Base schema for watchlist data, containing core fields."""

    profile_id: UUID = Field(
        ..., description="UUID of the profile that added the content to the list"
    )
    content_id: UUID = Field(..., description="UUID of the content added to the list")


class WatchlistCreate(WatchlistBase):
    """
    Create a watchlist item. `added_at` is set by the server (default now()).
    """


class WatchlistUpdate(BaseModel):
    """
    Allows changing only the content or profile if your business permits it (normally not changed).
    """

    profile_id: Optional[UUID] = None
    content_id: Optional[UUID] = None


class WatchlistOut(WatchlistBase, AuditOut):
    """Schema for output (read) operations, including audit and primary key fields."""

    id: UUID
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WatchlistListItem(BaseModel):
    """A simplified schema for watchlist data, typically used for lists or summaries."""

    id: UUID
    profile_id: UUID
    content_id: UUID
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)
