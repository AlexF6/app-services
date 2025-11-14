# app/api/v1/me_users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, PasswordChange

router = APIRouter(prefix="/me/users", tags=["Me (Users)"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


@router.get("", response_model=UserResponse)
def get_my_profile(me: User = Depends(get_current_user)):
    """
    Return the authenticated user's own profile.
    """
    return me


@router.put("", response_model=UserResponse)
def update_my_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Update the authenticated user's profile.
    - Allows updating only `name` and `email`.
    - Ignores/blocks `active` and `is_admin` even if provided.
    - Ensures email uniqueness.
    """
    if me.deleted_at is not None:
        raise HTTPException(status_code=403, detail="User is deleted")

    if payload.email and payload.email != me.email:
        exists = (
            db.query(User)
            .filter(User.email == payload.email, User.id != me.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Email already registered")

    if payload.name is not None:
        me.name = payload.name
    if payload.email is not None:
        me.email = payload.email


    me.updated_by = me.id
    db.commit()
    db.refresh(me)
    return me


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Change the authenticated user's password.
    Requires current password; sets new hashed password.
    """
    if me.deleted_at is not None:
        raise HTTPException(status_code=403, detail="User is deleted")

    if not verify_password(payload.current_password, me.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    me.password = get_password_hash(payload.new_password)
    me.updated_by = me.id
    db.commit()
    return None
