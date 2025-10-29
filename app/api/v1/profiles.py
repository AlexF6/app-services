from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin

from app.models.user import User
from app.models.profile import Profile

from app.schemas.profile import (
    ProfileCreate,
    ProfileUpdate,
    ProfileOut,
    ProfileListItem,
)

router = APIRouter(prefix="/profiles", tags=["Profiles"])

def _ensure_user(db: Session, user_id: UUID) -> None:
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")

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
def list_profiles(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    user_id: Optional[UUID] = Query(None),
    q: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[ProfileListItem]:
    query = db.query(Profile)
    if user_id:
        query = query.filter(Profile.user_id == user_id)
    if q:
        query = query.filter(Profile.name.ilike(f"%{q}%"))
    query = query.order_by(Profile.created_at.desc())
    return query.limit(limit).offset(offset).all()

@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Profile:
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return prof

@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Profile:
    _ensure_user(db, payload.user_id)
    if _exists_name_for_user(db, payload.user_id, payload.name):
        raise HTTPException(status_code=409, detail="Profile name already exists for this user")

    entity = Profile(
        user_id=payload.user_id,
        name=payload.name,
        avatar=payload.avatar,
        maturity_rating=payload.maturity_rating,
        created_by=admin.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity

@router.put("/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: UUID,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Profile:
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    if payload.name is not None and payload.name != prof.name:
        if _exists_name_for_user(db, prof.user_id, payload.name, exclude_id=prof.id):
            raise HTTPException(status_code=409, detail="Profile name already exists for this user")
        prof.name = payload.name

    if payload.avatar is not None:
        prof.avatar = payload.avatar or None
    if payload.maturity_rating is not None:
        prof.maturity_rating = payload.maturity_rating or None

    prof.updated_by = admin.id
    db.commit()
    db.refresh(prof)
    return prof

@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    db.delete(prof)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
