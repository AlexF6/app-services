from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base import AuditOut


class EpisodeBase(BaseModel):
    content_id: UUID = Field(
        ..., description="UUID of the content the episode belongs to"
    )
    season_number: int = Field(..., ge=1, description="Season number (>=1)")
    episode_number: int = Field(..., ge=1, description="Episode number (>=1)")
    title: str = Field(..., max_length=200, description="Episode title")
    duration_minutes: Optional[int] = Field(
        None, ge=1, description="Episode duration in minutes"
    )
    release_date: Optional[date] = Field(None, description="Episode release date")


class EpisodeCreate(EpisodeBase):
    """
    Create a new episode associated with an existing content.
    """


class EpisodeUpdate(BaseModel):
    """
    Partially update an episode.
    """

    season_number: Optional[int] = Field(None, ge=1)
    episode_number: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, max_length=200)
    duration_minutes: Optional[int] = Field(None, ge=1)
    release_date: Optional[date] = None


class EpisodeOut(EpisodeBase, AuditOut):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class EpisodeListItem(BaseModel):
    id: UUID
    content_id: UUID
    season_number: int
    episode_number: int
    title: str
    duration_minutes: Optional[int] = None
    release_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)
