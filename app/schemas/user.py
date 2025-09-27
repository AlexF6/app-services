from pydantic import BaseModel, EmailStr
import uuid

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

class UserResponse(UserBase):
    id: uuid.UUID

    class Config:
        from_attributes = True
