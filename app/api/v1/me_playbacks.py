# app/api/v1/me_playbacks.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.playback import Playback
from app.schemas.playback import PlaybackOut, PlaybackListItem

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
    profile_ids = [profile.id for profile in me.profiles]
    if not profile_ids:
        return []

    q = db.query(Playback).filter(Playback.profile_id.in_(profile_ids))

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
    playback.completed = True
    if playback.ended_at is None:
        playback.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(playback)
    return playback
