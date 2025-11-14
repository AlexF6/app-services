from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings

from app.api.v1.auth import get_current_user

from app.models.user import User
from app.models.profile import Profile

from app.schemas.profile import (
    ProfileCreateMe,
    ProfileUpdate,
    ProfileOut,
    ProfileListItem,
)

router = APIRouter(prefix="/me/profiles", tags=["Profiles (My)"])

def _profile_belongs_to(db: Session, profile_id: UUID, owner_id: UUID) -> Profile:
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    if prof.user_id != owner_id:
        raise HTTPException(status_code=403, detail="Profile does not belong to current user")
    return prof

def _exists_name_for_user(
    db: Session, user_id: UUID, name: str, exclude_id: Optional[UUID] = None
) -> bool:
    q = db.query(Profile).filter(
        Profile.user_id == user_id,
        func.lower(Profile.name) == name.lower(),
    )
    if exclude_id:
        q = q.filter(Profile.id != exclude_id)
    return db.query(q.exists()).scalar()

@router.get("", response_model=List[ProfileListItem])
def my_profiles(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    q: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[ProfileListItem]:
    query = db.query(Profile).filter(Profile.user_id == me.id)
    if q:
        query = query.filter(Profile.name.ilike(f"%{q}%"))
    query = query.order_by(Profile.created_at.desc())
    return query.limit(limit).offset(offset).all()

@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_my_profile(
    payload: ProfileCreateMe,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Profile:
    current_count = db.query(Profile).filter(Profile.user_id == me.id).count()
    if current_count >= settings.MAX_PROFILES_PER_USER:
        raise HTTPException(
            status_code=403,
            detail=f"Profile limit reached ({settings.MAX_PROFILES_PER_USER}).",
        )

    if _exists_name_for_user(db, me.id, payload.name):
        raise HTTPException(status_code=409, detail="Profile name already exists for this user")

    entity = Profile(
        user_id=me.id,
        name=payload.name,
        avatar=payload.avatar,
        maturity_rating=payload.maturity_rating,
        created_by=me.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity

@router.put("/{profile_id}", response_model=ProfileOut)
def update_my_profile(
    profile_id: UUID,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Profile:
    prof = _profile_belongs_to(db, profile_id, me.id)

    if payload.name is not None and payload.name != prof.name:
        if _exists_name_for_user(db, me.id, payload.name, exclude_id=prof.id):
            raise HTTPException(status_code=409, detail="Profile name already exists for this user")
        prof.name = payload.name

    if payload.avatar is not None:
        prof.avatar = payload.avatar or None
    if payload.maturity_rating is not None:
        prof.maturity_rating = payload.maturity_rating or None

    prof.updated_by = me.id
    db.commit()
    db.refresh(prof)
    return prof

@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Response:
    prof = _profile_belongs_to(db, profile_id, me.id)
    db.delete(prof)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
