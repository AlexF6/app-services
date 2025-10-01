from __future__ import annotations

from datetime import datetime, timezone
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
from app.models.content import Content
from app.models.episode import Episode  # si aún no lo tienes, comenta import y las validaciones de episodio
from app.models.playback import Playback

from app.schemas.playback import (
    PlaybackCreate,
    PlaybackUpdate,
    PlaybackOut,
    PlaybackListItem,
)

router = APIRouter(prefix="/playbacks", tags=["Playbacks"])
me_router = APIRouter(prefix="/profiles/{profile_id}/playbacks", tags=["Playbacks (My Profile)"])


# ----------------------------
# Helpers
# ----------------------------

def _ensure_profile(db: Session, profile_id: UUID) -> Profile:
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return prof

def _ensure_content(db: Session, content_id: UUID) -> Content:
    cnt = db.get(Content, content_id)
    if not cnt:
        raise HTTPException(status_code=404, detail="Content not found")
    return cnt

def _ensure_episode(db: Session, episode_id: Optional[UUID]) -> Optional[Episode]:
    if episode_id is None:
        return None
    ep = db.get(Episode, episode_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    return ep

def _ensure_episode_matches_content(ep: Episode, content_id: UUID) -> None:
    # Suponiendo Episode tiene content_id
    if getattr(ep, "content_id", None) != content_id:
        raise HTTPException(status_code=409, detail="Episode does not belong to given content")

def _profile_belongs_to_user(profile: Profile, user_id: UUID) -> None:
    if profile.user_id != user_id:
        raise HTTPException(status_code=403, detail="Profile does not belong to current user")

def _normalize_progress_and_completion(entity: Playback, upd_progress: Optional[int], upd_completed: Optional[bool], upd_ended_at: Optional[datetime]) -> None:
    # progress
    if upd_progress is not None:
        if upd_progress < 0:
            raise HTTPException(status_code=400, detail="progress_seconds must be >= 0")
        entity.progress_seconds = upd_progress

    # completed & ended_at rules:
    if upd_completed is not None:
        entity.completed = upd_completed
        if upd_completed and entity.ended_at is None and upd_ended_at is None:
            entity.ended_at = datetime.now(timezone.utc)

    if upd_ended_at is not None:
        entity.ended_at = upd_ended_at
        if upd_ended_at and not entity.completed:
            # si envían ended_at, asumimos que completó (puedes omitir si no lo deseas)
            entity.completed = True


# ============================================================
#                           ADMIN
# ============================================================

@router.get("", response_model=List[PlaybackListItem])
def list_playbacks(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    profile_id: Optional[UUID] = Query(None),
    content_id: Optional[UUID] = Query(None),
    episode_id: Optional[UUID] = Query(None),
    completed: Optional[bool] = Query(None),
    device_q: Optional[str] = Query(None, description="Filtro por dispositivo (ilike)"),
    started_from: Optional[datetime] = Query(None),
    started_to: Optional[datetime] = Query(None),
    ended_from: Optional[datetime] = Query(None),
    ended_to: Optional[datetime] = Query(None),
    min_progress: Optional[int] = Query(None, ge=0),
    max_progress: Optional[int] = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Lista playbacks con filtros y paginación (solo admin).
    """
    q = db.query(Playback)

    if profile_id:
        q = q.filter(Playback.profile_id == profile_id)
    if content_id:
        q = q.filter(Playback.content_id == content_id)
    if episode_id:
        q = q.filter(Playback.episode_id == episode_id)
    if completed is not None:
        q = q.filter(Playback.completed.is_(completed))
    if device_q:
        q = q.filter(func.lower(Playback.device).ilike(f"%{device_q.lower()}%"))

    if started_from:
        q = q.filter(Playback.started_at >= started_from)
    if started_to:
        q = q.filter(Playback.started_at <= started_to)
    if ended_from:
        q = q.filter(Playback.ended_at.is_not(None), Playback.ended_at >= ended_from)
    if ended_to:
        q = q.filter(Playback.ended_at.is_not(None), Playback.ended_at <= ended_to)

    if min_progress is not None:
        q = q.filter(Playback.progress_seconds >= min_progress)
    if max_progress is not None:
        q = q.filter(Playback.progress_seconds <= max_progress)

    q = q.order_by(Playback.started_at.desc(), Playback.fecha_creacion.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/{playback_id}", response_model=PlaybackOut)
def get_playback(
    playback_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    pb = db.get(Playback, playback_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playback not found")
    return pb


@router.post("", response_model=PlaybackOut, status_code=status.HTTP_201_CREATED)
def create_playback(
    payload: PlaybackCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Crea un playback (admin). Valida perfil, contenido y episodio (coherencia content-episode).
    """
    prof = _ensure_profile(db, payload.profile_id)
    cnt = _ensure_content(db, payload.content_id)
    ep = _ensure_episode(db, payload.episode_id)
    if ep:
        _ensure_episode_matches_content(ep, cnt.id)

    entity = Playback(
        profile_id=prof.id,
        content_id=cnt.id,
        episode_id=getattr(ep, "id", None),
        started_at=payload.started_at,      # si None, DB usa now()
        ended_at=payload.ended_at,
        progress_seconds=payload.progress_seconds or 0,
        completed=payload.completed or False,
        device=payload.device,
        creado_por=admin.id,
    )
    # Reglas de coherencia de progreso/completado:
    _normalize_progress_and_completion(entity, payload.progress_seconds, payload.completed, payload.ended_at)

    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/{playback_id}", response_model=PlaybackOut)
def update_playback(
    playback_id: UUID,
    payload: PlaybackUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    pb = db.get(Playback, playback_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playback not found")

    _normalize_progress_and_completion(pb, payload.progress_seconds, payload.completed, payload.ended_at)

    if payload.device is not None:
        pb.device = payload.device or None

    pb.actualizado_por = admin.id
    db.commit()
    db.refresh(pb)
    return pb


@router.delete("/{playback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playback(
    playback_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    pb = db.get(Playback, playback_id)
    if not pb:
        return None
    db.delete(pb)
    db.commit()
    return None


# ============================================================
#                  OWNER-SCOPED (PERFIL DEL USUARIO)
# ============================================================

@me_router.get("", response_model=List[PlaybackListItem])
def my_profile_playbacks(
    profile_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    content_id: Optional[UUID] = Query(None),
    episode_id: Optional[UUID] = Query(None),
    completed: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    prof = _ensure_profile(db, profile_id)
    _profile_belongs_to_user(prof, me.id)

    q = db.query(Playback).filter(Playback.profile_id == profile_id)
    if content_id:
        q = q.filter(Playback.content_id == content_id)
    if episode_id:
        q = q.filter(Playback.episode_id == episode_id)
    if completed is not None:
        q = q.filter(Playback.completed.is_(completed))

    q = q.order_by(Playback.started_at.desc(), Playback.fecha_creacion.desc())
    return q.limit(limit).offset(offset).all()


@me_router.post("", response_model=PlaybackOut, status_code=status.HTTP_201_CREATED)
def start_playback_for_my_profile(
    profile_id: UUID,
    payload: PlaybackCreate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Inicia un playback para un perfil del usuario autenticado.
    """
    prof = _ensure_profile(db, profile_id)
    _profile_belongs_to_user(prof, me.id)

    if payload.profile_id != profile_id:
        # reforzamos que el body apunte al mismo perfil de la ruta
        raise HTTPException(status_code=400, detail="profile_id mismatch with route parameter")

    cnt = _ensure_content(db, payload.content_id)
    ep = _ensure_episode(db, payload.episode_id)
    if ep:
        _ensure_episode_matches_content(ep, cnt.id)

    entity = Playback(
        profile_id=profile_id,
        content_id=cnt.id,
        episode_id=getattr(ep, "id", None),
        started_at=payload.started_at,  # DB pone now() si None
        ended_at=payload.ended_at,
        progress_seconds=payload.progress_seconds or 0,
        completed=payload.completed or False,
        device=payload.device,
        creado_por=me.id,
    )
    _normalize_progress_and_completion(entity, payload.progress_seconds, payload.completed, payload.ended_at)

    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@me_router.put("/{playback_id}", response_model=PlaybackOut)
def update_my_profile_playback(
    profile_id: UUID,
    playback_id: UUID,
    payload: PlaybackUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    prof = _ensure_profile(db, profile_id)
    _profile_belongs_to_user(prof, me.id)

    pb = db.get(Playback, playback_id)
    if not pb or pb.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Playback not found")

    _normalize_progress_and_completion(pb, payload.progress_seconds, payload.completed, payload.ended_at)

    if payload.device is not None:
        pb.device = payload.device or None

    pb.actualizado_por = me.id
    db.commit()
    db.refresh(pb)
    return pb


@me_router.post("/{playback_id}/finish", response_model=PlaybackOut)
def finish_my_profile_playback(
    profile_id: UUID,
    playback_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Marca un playback como completado (completed=True, ended_at=now si no existe).
    """
    prof = _ensure_profile(db, profile_id)
    _profile_belongs_to_user(prof, me.id)

    pb = db.get(Playback, playback_id)
    if not pb or pb.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Playback not found")

    if not pb.completed:
        pb.completed = True
    if pb.ended_at is None:
        pb.ended_at = datetime.now(timezone.utc)

    pb.actualizado_por = me.id
    db.commit()
    db.refresh(pb)
    return pb


@me_router.delete("/{playback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_profile_playback(
    profile_id: UUID,
    playback_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    prof = _ensure_profile(db, profile_id)
    _profile_belongs_to_user(prof, me.id)

    pb = db.get(Playback, playback_id)
    if not pb or pb.profile_id != profile_id:
        return None

    db.delete(pb)
    db.commit()
    return None
