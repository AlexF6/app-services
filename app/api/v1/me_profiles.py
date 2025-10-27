# app/api/v1/me_profiles.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.profile import Profile
from app.schemas.profile import (
    ProfileListItem,  # or ProfileListOut if you kept the alias
    ProfileOut,
    ProfileCreateMe,
    ProfileUpdate,
)

router = APIRouter(prefix="/me/profiles", tags=["Profiles"])

@router.get("", response_model=list[ProfileListItem])
def list_my_profiles(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    rows = (
        db.query(Profile)
        .filter(Profile.user_id == me.id)
        .order_by(Profile.created_at.desc())
        .all()
    )
    return rows

@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_my_profile(
    payload: ProfileCreateMe,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    # optional: enforce unique name per user
    exists = (
        db.query(Profile)
        .filter(Profile.user_id == me.id, Profile.name == payload.name)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Profile name already exists")

    obj = Profile(
        user_id=me.id,
        name=payload.name,
        avatar=payload.avatar,
        maturity_rating=payload.maturity_rating,
        created_by=me.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _ensure_owner(db: Session, me: User, profile_id: UUID) -> Profile:
    obj = db.get(Profile, profile_id)
    if not obj or obj.user_id != me.id:
        # 404 prevents leaking the existence of other users' profiles
        raise HTTPException(status_code=404, detail="Profile not found")
    return obj

@router.put("/{profile_id}", response_model=ProfileOut)
def update_my_profile(
    profile_id: UUID,
    patch: ProfileUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    obj = _ensure_owner(db, me, profile_id)

    # optional: uniqueness if changing name
    if patch.name and patch.name != obj.name:
        dup = (
            db.query(Profile)
            .filter(Profile.user_id == me.id, Profile.name == patch.name)
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="Profile name already exists")

    if patch.name is not None:
        obj.name = patch.name
    if patch.avatar is not None:
        obj.avatar = patch.avatar
    if patch.maturity_rating is not None:
        obj.maturity_rating = patch.maturity_rating

    obj.updated_by = me.id
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    obj = _ensure_owner(db, me, profile_id)
    db.delete(obj)
    db.commit()
    # FastAPI will render 204 automatically since status_code is set
