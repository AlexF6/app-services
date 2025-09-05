from pydantic import BaseModel, EmailStr
from typing import Optional

class User(BaseModel):
  id: int
  nombre: str
  email: Optional[EmailStr] = None
  activo: bool = True