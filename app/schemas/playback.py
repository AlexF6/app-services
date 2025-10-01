from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base import AuditOut


class PlaybackBase(BaseModel):
    """Base schema for playback data, containing all core fields."""

    profile_id: UUID = Field(..., description="Profile that performed the playback")
    content_id: UUID = Field(..., description="Content being played")
    episode_id: Optional[UUID] = Field(
        None, description="Episode being played (if applicable, for series)"
    )
    started_at: Optional[datetime] = Field(
        None, description="Date and time the playback started"
    )
    ended_at: Optional[datetime] = Field(
        None, description="Date and time the playback ended"
    )
    progress_seconds: Optional[int] = Field(
        0, ge=0, description="Seconds played so far"
    )
    completed: Optional[bool] = Field(
        False, description="True if the content was finished watching"
    )
    device: Optional[str] = Field(
        None, max_length=80, description="Device from which the content is played"
    )


class PlaybackCreate(PlaybackBase):
    """
    Create a new playback record.
    - If `started_at` is not sent, the current date will be used.
    """


class PlaybackUpdate(BaseModel):
    """
    Partially update a playback record.
    """

    ended_at: Optional[datetime] = None
    progress_seconds: Optional[int] = Field(None, ge=0)
    completed: Optional[bool] = None
    device: Optional[str] = Field(None, max_length=80)


class PlaybackOut(PlaybackBase, AuditOut):
    """Schema for output (read) operations, including audit and primary key fields."""

    id: UUID
    started_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlaybackListItem(BaseModel):
    """A simplified schema for playback data, typically used for lists or summaries."""

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
