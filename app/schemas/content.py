from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.auditmixin import ContentType
from app.schemas.base import AuditOut


class ContentBase(BaseModel):
    title: str = Field(..., max_length=200, description="Title of the work (series/movie/documentary)")
    type: ContentType = Field(..., description="Content type (MOVIE, SERIES, DOCUMENTARY, etc.)")
    description: Optional[str] = Field(None, description="Optional description")
    release_year: Optional[int] = Field(None, ge=1800, le=2100, description="Release year")
    duration_minutes: Optional[int] = Field(None, ge=1, description="Total duration in minutes (for movies or episodes)")
    age_rating: Optional[str] = Field(None, max_length=10, description="Age rating (e.g. PG-13, TV-MA)")
    genres: Optional[str] = Field(None, description="Comma-separated genres (e.g. Drama, Action, Fantasy)")
    video_url: Optional[str] = Field(None, description="Remote video URL (MP4/M3U8/etc.)")
    thumbnail: Optional[str] = Field(None, description="Thumbnail image URL")


class ContentCreate(ContentBase):
    """Create content. `title` and `type` are required."""


class ContentUpdate(BaseModel):
    """Partial update of content."""
    title: Optional[str] = Field(None, max_length=200)
    type: Optional[ContentType] = None
    description: Optional[str] = None
    release_year: Optional[int] = Field(None, ge=1800, le=2100)
    duration_minutes: Optional[int] = Field(None, ge=1)
    age_rating: Optional[str] = Field(None, max_length=10)
    genres: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail: Optional[str] = None


class ContentOut(AuditOut, ContentBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class ContentListItem(BaseModel):
    id: UUID
    title: str
    type: ContentType
    release_year: Optional[int] = None
    age_rating: Optional[str] = None
    genres: Optional[str] = None
    duration_minutes: Optional[int] = None
    thumbnail: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
