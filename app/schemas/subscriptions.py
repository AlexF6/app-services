from pydantic import BaseModel
from typing import Optional


class Subscription(BaseModel):
    id: int
    user_id: int
    plan: str
    active: bool = True
