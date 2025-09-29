from fastapi import Depends, HTTPException, status
from app.api.v1.auth import get_current_user
from app.models.user import User


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return current_user
