from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from typing import List, Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserResponse, UserCreateAdmin, UserUpdate,
    PasswordChange, PasswordSetAdmin
)
from app.api.v1.auth import get_current_user
from app.api.deps import require_admin
from passlib.context import CryptContext

router = APIRouter(prefix="/users", tags=["Users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, description="Filtrar por nombre o email"),
    include_deleted: bool = Query(False),
    only_active: bool = Query(False),
):
    query = db.query(User)
    if not include_deleted:
        query = query.filter(User.deleted_at.is_(None))
    if only_active:
        query = query.filter(User.active.is_(True))
    if q:
        query = query.filter((User.name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%")))
    users = query.order_by(User.fecha_creacion.desc()).limit(limit).offset(offset).all()
    return users

@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    include_deleted: bool = Query(False),
):
    user = db.get(User, user_id)
    if not user or (not include_deleted and user.deleted_at is not None):
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateAdmin,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    new_id = uuid4()
    user = User(
        id=new_id,
        name=payload.name,
        email=payload.email,
        password=get_password_hash(payload.password),
        active=payload.active,
        is_admin=payload.is_admin,
        creado_por=admin.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.email and payload.email != user.email:
        if db.query(User).filter(User.email == payload.email, User.id != user.id).first():
            raise HTTPException(status_code=409, detail="Email already registered")

    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = payload.email
    if payload.active is not None:
        user.active = payload.active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin

    user.actualizado_por = admin.id
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        return None
    user.deleted_at = datetime.now(timezone.utc)
    user.actualizado_por = admin.id
    db.commit()
    return None

@router.post("/{user_id}/restore", response_model=UserResponse)
def restore_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user or user.deleted_at is None:
        raise HTTPException(status_code=404, detail="User not found or not deleted")
    user.deleted_at = None
    user.actualizado_por = admin.id
    db.commit()
    db.refresh(user)
    return user

@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    if me.deleted_at is not None:
        raise HTTPException(status_code=403, detail="User is deleted")
    if not verify_password(payload.current_password, me.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    me.password = get_password_hash(payload.new_password)
    me.actualizado_por = me.id
    db.commit()
    return None

@router.post("/{user_id}/set-password", status_code=status.HTTP_204_NO_CONTENT)
def set_user_password_admin(
    user_id: UUID,
    payload: PasswordSetAdmin,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password = get_password_hash(payload.new_password)
    user.actualizado_por = admin.id
    db.commit()
    return None
