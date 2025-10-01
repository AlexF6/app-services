from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base import AuditOut


class PlanBase(BaseModel):
    """Base schema for plan data, containing core configuration fields."""

    name: str = Field(..., min_length=1, max_length=80, description="Name of the plan")
    price: Decimal = Field(..., gt=0, description="Monthly or cycle price")
    max_profiles: int = Field(
        1, ge=1, description="Maximum number of allowed profiles"
    )
    max_devices: int = Field(
        1, ge=1, description="Maximum number of allowed devices"
    )
    video_quality: str = Field(
        "HD", max_length=20, description="Video quality (e.g., SD, HD, UHD, 4K)"
    )


class PlanCreate(PlanBase):
    """
    Schema for creating a new plan.

    Constraints: price > 0, max_profiles/devices >= 1.
    """


class PlanUpdate(BaseModel):
    """
    Schema for partial update of an existing plan.
    """

    name: Optional[str] = Field(None, max_length=80)
    price: Optional[Decimal] = Field(None, gt=0)
    max_profiles: Optional[int] = Field(None, ge=1)
    max_devices: Optional[int] = Field(None, ge=1)
    video_quality: Optional[str] = Field(None, max_length=20)


class PlanOut(PlanBase, AuditOut):
    """Schema for output (read) operations, including audit and primary key fields."""

    id: UUID

    model_config = ConfigDict(from_attributes=True)


class PlanListItem(BaseModel):
    """A simplified schema for plan data, typically used for lists or summaries."""

    id: UUID
    name: str
    price: Decimal
    max_profiles: int
    max_devices: int
    video_quality: str

    model_config = ConfigDict(from_attributes=True)