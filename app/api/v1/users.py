from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from typing import List, Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    UserCreateAdmin,
    UserUpdate,
    PasswordChange,
    PasswordSetAdmin,
)
from app.api.v1.auth import get_current_user
from app.api.deps import require_admin
from passlib.context import CryptContext

router = APIRouter(prefix="/users", tags=["Users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Generates a secure hash for a given password using the bcrypt scheme.

    Args:
        password: The plaintext password to hash.

    Returns:
        The password hash as a string.
    """
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verifies a plaintext password against a hashed password.

    Args:
        plain: The plaintext password provided by the user.
        hashed: The stored hashed password.

    Returns:
        True if the passwords match, False otherwise.
    """
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
    """
    Retrieves a paginated list of users.

    Requires administrator privileges. Allows filtering by search query (name/email),
    inclusion of soft-deleted users, and filtering only active users.

    Args:
        db: Dependency providing the database session.
        _: Dependency to ensure the user has admin privileges.
        limit: Maximum number of users to return.
        offset: Number of users to skip for pagination.
        q: Optional search string to filter by name or email.
        include_deleted: If True, includes soft-deleted users.
        only_active: If True, filters for only active users.

    Returns:
        A list of UserResponse objects.
    """
    query = db.query(User)
    if not include_deleted:
        query = query.filter(User.deleted_at.is_(None))
    if only_active:
        query = query.filter(User.active.is_(True))
    if q:
        query = query.filter((User.name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%")))
    users = query.order_by(User.created_at.desc()).limit(limit).offset(offset).all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    include_deleted: bool = Query(False),
):
    """
    Retrieves a single user by their ID.

    Requires administrator privileges. Optionally includes soft-deleted users.

    Args:
        user_id: The UUID of the user to retrieve.
        db: Dependency providing the database session.
        _: Dependency to ensure the user has admin privileges.
        include_deleted: If True, allows fetching a soft-deleted user.

    Raises:
        HTTPException: 404 Not Found if the user does not exist or is deleted
                       and include_deleted is False.

    Returns:
        The requested UserResponse object.
    """
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
    """
    Creates a new user with administrative privileges.

    Requires administrator privileges. Checks for email conflicts before creation.

    Args:
        payload: Data for the new user, including password, active status, and admin flag.
        db: Dependency providing the database session.
        admin: The currently authenticated administrator user.

    Raises:
        HTTPException: 409 Conflict if the email is already registered.

    Returns:
        The newly created UserResponse object.
    """
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
        created_by=admin.id,
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
    """
    Updates an existing user's details.

    Requires administrator privileges. Prevents updating soft-deleted users and
    checks for email conflicts if the email is changed.

    Args:
        user_id: The UUID of the user to update.
        payload: The fields to update (name, email, active, is_admin).
        db: Dependency providing the database session.
        admin: The currently authenticated administrator user.

    Raises:
        HTTPException: 404 Not Found if the user does not exist or is deleted.
        HTTPException: 409 Conflict if the new email is already registered by another user.

    Returns:
        The updated UserResponse object.
    """
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.email and payload.email != user.email:
        if (
            db.query(User)
            .filter(User.email == payload.email, User.id != user.id)
            .first()
        ):
            raise HTTPException(status_code=409, detail="Email already registered")

    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = payload.email
    if payload.active is not None:
        user.active = payload.active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin

    user.updated_by = admin.id
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Performs a soft delete on a user (marks as deleted with a timestamp).

    Requires administrator privileges. If the user is already deleted, it returns 204.

    Args:
        user_id: The UUID of the user to soft-delete.
        db: Dependency providing the database session.
        admin: The currently authenticated administrator user.

    Returns:
        None (HTTP 204 No Content) upon successful soft deletion or if the user was already deleted.
    """
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        return None
    user.deleted_at = datetime.now(timezone.utc)
    user.active = False
    user.updated_by = admin.id
    db.commit()
    return None


@router.post("/{user_id}/restore", response_model=UserResponse)
def restore_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Restores a soft-deleted user by clearing the deleted_at timestamp.

    Requires administrator privileges.

    Args:
        user_id: The UUID of the user to restore.
        db: Dependency providing the database session.
        admin: The currently authenticated administrator user.

    Raises:
        HTTPException: 404 Not Found if the user does not exist or is not currently deleted.

    Returns:
        The restored UserResponse object.
    """
    user = db.get(User, user_id)
    if not user or user.deleted_at is None:
        raise HTTPException(status_code=404, detail="User not found or not deleted")
    user.deleted_at = None
    user.updated_by = admin.id
    user.active = True
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Allows the currently authenticated user to change their own password.

    Requires the user to provide their current password for verification.

    Args:
        payload: Contains the current password and the new password.
        db: Dependency providing the database session.
        me: The currently authenticated user object.

    Raises:
        HTTPException: 403 Forbidden if the user is deleted.
        HTTPException: 400 Bad Request if the current password is incorrect.

    Returns:
        None (HTTP 204 No Content) upon successful password change.
    """
    if me.deleted_at is not None:
        raise HTTPException(status_code=403, detail="User is deleted")
    if not verify_password(payload.current_password, me.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    me.password = get_password_hash(payload.new_password)
    me.updated_by = me.id
    db.commit()
    return None


@router.post("/{user_id}/set-password", status_code=status.HTTP_204_NO_CONTENT)
def set_user_password_admin(
    user_id: UUID,
    payload: PasswordSetAdmin,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Allows an administrator to set a new password for any user.

    Requires administrator privileges. Does not require the user's current password.

    Args:
        user_id: The UUID of the user whose password is to be changed.
        payload: Contains the new password to set.
        db: Dependency providing the database session.
        admin: The currently authenticated administrator user.

    Raises:
        HTTPException: 404 Not Found if the user does not exist or is deleted.

    Returns:
        None (HTTP 204 No Content) upon successful password update.
    """
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password = get_password_hash(payload.new_password)
    user.updated_by = admin.id
    db.commit()
    return None
