from uuid import UUID
from pydantic import BaseModel

class MessageResponse(BaseModel):
    message: str


class TokenData(BaseModel):
    user_id: UUID | None = None