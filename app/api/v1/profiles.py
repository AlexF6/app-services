from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin
from app.api.v1.auth import get_current_user

from app.models.user import User
from app.models.profile import Profile

from app.schemas.profile import (
    ProfileCreate,
    ProfileUpdate,
    ProfileOut,
    ProfileListItem,
)

router = APIRouter(prefix="/profiles", tags=["Profiles"])
me_router = APIRouter(prefix="/me/profiles", tags=["Profiles (My)"])


# ----------------------------
# Helpers
# ----------------------------
def _ensure_user(db: Session, user_id: UUID) -> None:
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")


def _profile_belongs_to(db: Session, profile_id: UUID, owner_id: UUID) -> Profile:
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    if prof.user_id != owner_id:
        raise HTTPException(status_code=403, detail="Profile does not belong to current user")
    return prof


def _exists_name_for_user(db: Session, user_id: UUID, name: str, exclude_id: Optional[UUID] = None) -> bool:
    q = db.query(Profile).filter(
        Profile.user_id == user_id,
        func.lower(Profile.name) == name.lower(),
    )
    if exclude_id:
        q = q.filter(Profile.id != exclude_id)
    return db.query(q.exists()).scalar()


# ============================================================
#                          ADMIN
# ============================================================

@router.get("", response_model=List[ProfileListItem])
def list_profiles(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    user_id: Optional[UUID] = Query(None),
    q: Optional[str] = Query(None, description="Buscar por nombre (ilike)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Lista perfiles con filtros (admin).
    """
    query = db.query(Profile)
    if user_id:
        query = query.filter(Profile.user_id == user_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(func.lower(Profile.name).ilike(like))

    query = query.order_by(Profile.fecha_creacion.desc())
    return query.limit(limit).offset(offset).all()


@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return prof


@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Crea un perfil para un usuario (admin). Enforce opcional: nombre único por usuario.
    """
    _ensure_user(db, payload.user_id)

    if _exists_name_for_user(db, payload.user_id, payload.name):
        raise HTTPException(status_code=409, detail="Profile name already exists for this user")

    entity = Profile(
        user_id=payload.user_id,
        name=payload.name,
        avatar=payload.avatar,
        maturity_rating=payload.maturity_rating,
        creado_por=admin.id,
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
):
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Si cambia el nombre, aplicar unicidad por usuario
    if payload.name is not None and payload.name != prof.name:
        if _exists_name_for_user(db, prof.user_id, payload.name, exclude_id=prof.id):
            raise HTTPException(status_code=409, detail="Profile name already exists for this user")
        prof.name = payload.name

    if payload.avatar is not None:
        prof.avatar = payload.avatar or None
    if payload.maturity_rating is not None:
        prof.maturity_rating = payload.maturity_rating or None

    prof.actualizado_por = admin.id
    db.commit()
    db.refresh(prof)
    return prof


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    prof = db.get(Profile, profile_id)
    if not prof:
        return None
    db.delete(prof)
    db.commit()
    return None


# ============================================================
#                   CURRENT USER ("MY PROFILES")
# ============================================================

@me_router.get("", response_model=List[ProfileListItem])
def my_profiles(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    q: Optional[str] = Query(None, description="Buscar por nombre (ilike)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = db.query(Profile).filter(Profile.user_id == me.id)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(func.lower(Profile.name).ilike(like))

    query = query.order_by(Profile.fecha_creacion.desc())
    return query.limit(limit).offset(offset).all()


@me_router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_my_profile(
    payload: ProfileUpdate,  # reusa campos name/avatar/maturity_rating
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Crea un perfil para el usuario autenticado.
    """
    if not payload.name:
        raise HTTPException(status_code=400, detail="name is required")

    if _exists_name_for_user(db, me.id, payload.name):
        raise HTTPException(status_code=409, detail="Profile name already exists for this user")

    entity = Profile(
        user_id=me.id,
        name=payload.name,
        avatar=payload.avatar,
        maturity_rating=payload.maturity_rating,
        creado_por=me.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@me_router.put("/{profile_id}", response_model=ProfileOut)
def update_my_profile(
    profile_id: UUID,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    prof = _profile_belongs_to(db, profile_id, me.id)

    if payload.name is not None and payload.name != prof.name:
        if _exists_name_for_user(db, me.id, payload.name, exclude_id=prof.id):
            raise HTTPException(status_code=409, detail="Profile name already exists for this user")
        prof.name = payload.name

    if payload.avatar is not None:
        prof.avatar = payload.avatar or None
    if payload.maturity_rating is not None:
        prof.maturity_rating = payload.maturity_rating or None

    prof.actualizado_por = me.id
    db.commit()
    db.refresh(prof)
    return prof


@me_router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    prof = _profile_belongs_to(db, profile_id, me.id)
    db.delete(prof)
    db.commit()
    return None
