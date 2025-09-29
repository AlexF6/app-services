from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
import uuid
from typing import Optional
from app.schemas.base import AuditOut


class UserBase(BaseModel):
    name: str
    email: EmailStr
    active: bool = True


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    active: Optional[bool] = None
    is_admin: Optional[bool] = None


class UserCreateAdmin(BaseModel):
    name: str
    email: EmailStr
    password: str
    active: bool = True
    is_admin: bool = False


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=6)
    new_password: str = Field(min_length=6)


class PasswordSetAdmin(BaseModel):
    new_password: str = Field(min_length=6)


class UserResponse(UserBase):
    id: uuid.UUID
    is_admin: bool = False
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
