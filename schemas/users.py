from pydantic import BaseModel, EmailStr
from typing import Optional

class User(BaseModel):
  id: int
  name: str
  email: Optional[EmailStr] = None
  active: bool = True