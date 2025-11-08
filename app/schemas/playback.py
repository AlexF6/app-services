# app/schemas/playback.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
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
        None, max_length=200, description="Device from which the content is played"
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
    device: Optional[str] = Field(None, max_length=200)



class PlaybackOut(PlaybackBase, AuditOut):
    """Schema for output (read) operations, including audit and primary key fields."""

    id: UUID
    started_at: datetime
    duration_seconds: Optional[int] = None
    # útil para mostrar "visto por última vez"
    last_seen_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class PlaybackListItem(BaseModel):
    id: UUID
    profile_id: UUID
    content_id: UUID
    episode_id: Optional[UUID]
    started_at: datetime
    ended_at: Optional[datetime]
    progress_seconds: int
    duration_seconds: Optional[int] = None
    completed: bool
    device: Optional[str]
    last_seen_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class PlaybackStartMe(BaseModel):
    profile_id: UUID
    content_id: Optional[UUID] = None
    episode_id: Optional[UUID] = None
    device: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _ensure_one_target(self):
        # Requiere al menos uno: content o episode
        if not self.content_id and not self.episode_id:
            raise ValueError("Provide content_id or episode_id")
        return self


class PlaybackUpdateMe(BaseModel):
    # nombre consistente con tu modelo actual
    progress_seconds: int = Field(ge=0)
    duration_seconds: Optional[int] = Field(default=None, ge=0)
    completed: Optional[bool] = None