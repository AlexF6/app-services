from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin
from app.api.v1.auth import get_current_user

from app.models.user import User
from app.models.profile import Profile
from app.models.content import Content
from app.models.watchlist import Watchlist

from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistUpdate,
    WatchlistOut,
    WatchlistListItem,
)

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


# ----------------------------
# Helpers
# ----------------------------
def _ensure_profile_and_content(db: Session, profile_id: UUID, content_id: UUID) -> None:
    if not db.get(Profile, profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    if not db.get(Content, content_id):
        raise HTTPException(status_code=404, detail="Content not found")


def _ensure_profile_belongs_to_user(db: Session, profile_id: UUID, user_id: UUID) -> Profile:
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    if prof.user_id != user_id:
        raise HTTPException(status_code=403, detail="Profile does not belong to current user")
    return prof


def _exists_watchlist_item(db: Session, profile_id: UUID, content_id: UUID) -> bool:
    return (
        db.query(Watchlist)
        .filter(Watchlist.profile_id == profile_id, Watchlist.content_id == content_id)
        .first()
        is not None
    )


# ============================================================
#                           ADMIN
# ============================================================

@router.get("", response_model=List[WatchlistListItem])
def list_watchlist_items(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    profile_id: Optional[UUID] = Query(None),
    content_id: Optional[UUID] = Query(None),
    added_from: Optional[datetime] = Query(None),
    added_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Lista ítems de watchlist (admin).
    """
    q = db.query(Watchlist)

    if profile_id:
        q = q.filter(Watchlist.profile_id == profile_id)
    if content_id:
        q = q.filter(Watchlist.content_id == content_id)
    if added_from:
        q = q.filter(Watchlist.added_at >= added_from)
    if added_to:
        q = q.filter(Watchlist.added_at <= added_to)

    q = q.order_by(Watchlist.added_at.desc(), Watchlist.fecha_creacion.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/{watchlist_id}", response_model=WatchlistOut)
def get_watchlist_item(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    item = db.get(Watchlist, watchlist_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def create_watchlist_item(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Crea un ítem de watchlist (admin). Evita duplicados profile_id+content_id.
    """
    _ensure_profile_and_content(db, payload.profile_id, payload.content_id)

    if _exists_watchlist_item(db, payload.profile_id, payload.content_id):
        raise HTTPException(status_code=409, detail="Item already exists in watchlist")

    entity = Watchlist(
        profile_id=payload.profile_id,
        content_id=payload.content_id,
        creado_por=admin.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/{watchlist_id}", response_model=WatchlistOut)
def update_watchlist_item(
    watchlist_id: UUID,
    payload: WatchlistUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Actualiza un ítem de watchlist (admin). No recomendado cambiar profile_id;
    si lo permites, validamos referencias y duplicados.
    """
    entity = db.get(Watchlist, watchlist_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    new_profile_id = payload.profile_id or entity.profile_id
    new_content_id = payload.content_id or entity.content_id

    _ensure_profile_and_content(db, new_profile_id, new_content_id)

    # si cambian a una combinación existente, conflicto
    if (new_profile_id != entity.profile_id) or (new_content_id != entity.content_id):
        if _exists_watchlist_item(db, new_profile_id, new_content_id):
            raise HTTPException(status_code=409, detail="Item already exists in watchlist")
        entity.profile_id = new_profile_id
        entity.content_id = new_content_id

    entity.actualizado_por = admin.id
    db.commit()
    db.refresh(entity)
    return entity


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    entity = db.get(Watchlist, watchlist_id)
    if not entity:
        return None
    db.delete(entity)
    db.commit()
    return None


# ============================================================
#                    OWNER-SCOPED (PERFILES)
# ============================================================

profile_router = APIRouter(prefix="/profiles/{profile_id}/watchlist", tags=["Watchlist (My Profile)"])


class WatchlistQuickAdd(BaseModel):
    content_id: UUID


@profile_router.get("", response_model=List[WatchlistListItem])
def my_profile_watchlist(
    profile_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    q_title: Optional[str] = Query(None, description="Buscar por título de contenido (ilike)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Lista la watchlist del perfil del usuario autenticado.
    """
    _ensure_profile_belongs_to_user(db, profile_id, me.id)

    q = db.query(Watchlist).filter(Watchlist.profile_id == profile_id)

    if q_title:
        like = f"%{q_title.lower()}%"
        q = q.join(Content, Content.id == Watchlist.content_id).filter(
            func.lower(Content.title).ilike(like)
        )

    q = q.order_by(Watchlist.added_at.desc(), Watchlist.fecha_creacion.desc())
    return q.limit(limit).offset(offset).all()


@profile_router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def add_to_my_profile_watchlist(
    profile_id: UUID,
    payload: WatchlistQuickAdd,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Agrega un contenido a la watchlist del perfil del usuario autenticado.
    Idempotente: si ya existe, devuelve 409.
    """
    _ensure_profile_belongs_to_user(db, profile_id, me.id)

    _ensure_profile_and_content(db, profile_id, payload.content_id)

    if _exists_watchlist_item(db, profile_id, payload.content_id):
        raise HTTPException(status_code=409, detail="Item already exists in watchlist")

    entity = Watchlist(
        profile_id=profile_id,
        content_id=payload.content_id,
        creado_por=me.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@profile_router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_my_profile_watchlist(
    profile_id: UUID,
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Elimina un ítem de la watchlist del perfil del usuario autenticado.
    """
    _ensure_profile_belongs_to_user(db, profile_id, me.id)

    entity = db.get(Watchlist, watchlist_id)
    if not entity or entity.profile_id != profile_id:
        return None

    db.delete(entity)
    db.commit()
    return None


@profile_router.delete("/by-content/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_by_content_from_my_profile_watchlist(
    profile_id: UUID,
    content_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Elimina por content_id (conveniencia). No falla si no existe.
    """
    _ensure_profile_belongs_to_user(db, profile_id, me.id)

    entity = (
        db.query(Watchlist)
        .filter(Watchlist.profile_id == profile_id, Watchlist.content_id == content_id)
        .first()
    )
    if not entity:
        return None

    db.delete(entity)
    db.commit()
    return None
