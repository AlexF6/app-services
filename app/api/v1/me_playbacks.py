# app/api/v1/me_playbacks.py
from __future__ import annotations

from datetime import datetime, timezone
from sqlite3 import IntegrityError
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.episode import Episode
from app.models.user import User
from app.models.playback import Playback
from app.schemas.playback import PlaybackOut, PlaybackListItem, PlaybackStartMe, PlaybackUpdateMe

router = APIRouter(prefix="/me/playbacks", tags=["Playbacks (Me)"])


def _ensure_owner(db: Session, me: User, playback_id: UUID) -> Playback:
    """Ensure the playback belongs to one of the user's profiles."""
    playback = db.get(Playback, playback_id)
    if not playback:
        raise HTTPException(status_code=404, detail="Playback not found")

    user_profile_ids = [profile.id for profile in me.profiles]
    if playback.profile_id not in user_profile_ids:
        # Hide existence
        raise HTTPException(status_code=404, detail="Playback not found")

    return playback


@router.get("", response_model=List[PlaybackListItem])
def list_my_playbacks(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),

    # 👇 AÑADE ESTE PARÁMETRO
    profile_id: Optional[UUID] = Query(
        None, description="Filter by a specific owned profile"
    ),

    completed: Optional[bool] = Query(None, description="Filter by completion status"),
    device: Optional[str] = Query(None, description="Filter by device name"),
    content_id: Optional[UUID] = Query(None, description="Filter by specific content"),
    episode_id: Optional[UUID] = Query(None, description="Filter by specific episode"),
    started_from: Optional[datetime] = Query(None, description="Filter by start date from"),
    started_to: Optional[datetime] = Query(None, description="Filter by start date to"),
    ended_from: Optional[datetime] = Query(None, description="Filter by end date from"),
    ended_to: Optional[datetime] = Query(None, description="Filter by end date to"),
    min_progress: Optional[int] = Query(None, ge=0, description="Minimum progress in seconds"),
    max_progress: Optional[int] = Query(None, ge=0, description="Maximum progress in seconds"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    profile_ids = [p.id for p in me.profiles]
    if not profile_ids:
        return []

    # ✅ Validación de pertenencia cuando llega profile_id
    if profile_id is not None and profile_id not in profile_ids:
        # 404 para no filtrar existencia de otros perfiles
        raise HTTPException(status_code=404, detail="Profile not found")

    # ✅ Base query: si llega profile_id usa ese; si no, todos los del usuario
    allowed_ids = [profile_id] if profile_id is not None else profile_ids
    q = db.query(Playback).filter(Playback.profile_id.in_(allowed_ids))

    if completed is not None:
        q = q.filter(Playback.completed.is_(completed))
    if device:
        q = q.filter(Playback.device.ilike(f"%{device}%"))
    if content_id:
        q = q.filter(Playback.content_id == content_id)
    if episode_id:
        q = q.filter(Playback.episode_id == episode_id)
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

    q = q.order_by(Playback.started_at.desc().nullslast(), Playback.created_at.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/{playback_id}", response_model=PlaybackOut)
def get_my_playback(
    playback_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    return _ensure_owner(db, me, playback_id)


@router.delete("/{playback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_playback(
    playback_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    playback = _ensure_owner(db, me, playback_id)
    db.delete(playback)
    db.commit()
    return None


@router.post("/{playback_id}/complete", response_model=PlaybackOut)
def mark_playback_completed(
    playback_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    playback = _ensure_owner(db, me, playback_id)
    now = datetime.now(timezone.utc)

    playback.completed = True
    if playback.ended_at is None:
        playback.ended_at = now

    playback.updated_by = me.id
    playback.updated_at = now

    db.commit()
    db.refresh(playback)
    return playback

@router.post("/start", response_model=PlaybackOut)
def start_my_playback(
    payload: PlaybackStartMe,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    user_profile_ids = [p.id for p in me.profiles]
    if payload.profile_id not in user_profile_ids:
        raise HTTPException(status_code=404, detail="Profile not found")

    now = datetime.now(timezone.utc)
    device = (payload.device or "unknown").strip().lower()[:200]

    # resolver content_id con episode_id
    content_id = payload.content_id
    episode_id = payload.episode_id
    if episode_id and not content_id:
        ep = db.get(Episode, episode_id)
        if not ep:
            raise HTTPException(status_code=404, detail="Episode not found")
        content_id = ep.content_id

    # 1) ¿Existe una sesión ABIERTA para (profile, content, episode)?
    pb = (
        db.query(Playback)
        .filter(
            Playback.profile_id == payload.profile_id,
            Playback.completed.is_(False),
            Playback.content_id == content_id,
            Playback.episode_id.is_(episode_id if episode_id else None),
        )
        .order_by(Playback.created_at.desc())
        .first()
    )
    if pb:
        # refresca tiempos/device
        pb.started_at = pb.started_at or now
        pb.last_seen_at = now
        pb.device = device
        pb.updated_by = me.id
        pb.updated_at = now
        db.commit(); db.refresh(pb)
        return pb

    # 2) No hay abierta → ¿hay una sesión previa (completada)?
    last_pb = (
        db.query(Playback)
        .filter(
            Playback.profile_id == payload.profile_id,
            Playback.content_id == content_id,
            Playback.episode_id.is_(episode_id if episode_id else None),
        )
        .order_by(Playback.created_at.desc())
        .first()
    )
    if last_pb:
        # Re-abrir MISMA FILA (no crear otra)
        last_pb.completed = False
        last_pb.progress_seconds = 0
        last_pb.duration_seconds = None
        last_pb.started_at = now
        last_pb.ended_at = None
        last_pb.last_seen_at = now
        last_pb.device = device
        last_pb.updated_by = me.id
        last_pb.updated_at = now
        db.commit(); db.refresh(last_pb)
        return last_pb

    # 3) No existe ninguna → crear
    pb = Playback(
        profile_id=payload.profile_id,
        content_id=content_id,
        episode_id=episode_id,
        device=device,
        started_at=now,
        last_seen_at=now,
        completed=False,
        progress_seconds=0,
        duration_seconds=None,
        created_by=me.id,
        updated_by=me.id,
        updated_at=now,
    )
    db.add(pb)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # carrera: trae la existente (abierta o reabierta)
        pb = (
            db.query(Playback)
            .filter(
                Playback.profile_id == payload.profile_id,
                Playback.content_id == content_id,
                Playback.episode_id.is_(episode_id if episode_id else None),
            )
            .order_by(Playback.created_at.desc())
            .first()
        )
        if not pb:
            raise
    db.refresh(pb)
    return pb

@router.patch("/{playback_id}", response_model=PlaybackOut)
def update_my_playback(
    playback_id: UUID,
    patch: PlaybackUpdateMe,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    playback = _ensure_owner(db, me, playback_id)
    now = datetime.now(timezone.utc)

    # -- duration: mantén el mayor conocido (evita caer a 0/None por lecturas tempranas)
    if patch.duration_seconds is not None:
        new_dur = max(0, patch.duration_seconds)
        if not playback.duration_seconds or new_dur > playback.duration_seconds:
            playback.duration_seconds = new_dur

    # -- clamp & anti-regresión de progreso
    incoming = max(0, patch.progress_seconds)
    if playback.duration_seconds:
        incoming = min(incoming, playback.duration_seconds)

    # nunca disminuir progreso
    new_progress = max(playback.progress_seconds or 0, incoming)
    playback.progress_seconds = new_progress

    playback.last_seen_at = now

    # autocompletar 95%
    dur = playback.duration_seconds or 0
    if dur > 0 and playback.progress_seconds >= int(0.95 * dur):
        playback.completed = True
        if playback.ended_at is None:
            playback.ended_at = now

    # completed explícito
    if patch.completed is True:
        playback.completed = True
        if playback.ended_at is None:
            playback.ended_at = now

    playback.updated_by = me.id
    playback.updated_at = now

    db.commit()
    db.refresh(playback)
    return playback