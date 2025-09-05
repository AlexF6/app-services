from pydantic import BaseModel, EmailStr
from typing import Optional

class Serie(BaseModel):
  id: int
  name: str
  seasons: int
  active: bool = True