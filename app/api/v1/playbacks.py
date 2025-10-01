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
from app.models.episode import Episode
from app.models.playback import Playback

from app.schemas.playback import (
    PlaybackCreate,
    PlaybackUpdate,
    PlaybackOut,
    PlaybackListItem,
)

router = APIRouter(prefix="/playbacks", tags=["Playbacks"])
me_router = APIRouter(
    prefix="/profiles/{profile_id}/playbacks", tags=["Playbacks (My Profile)"]
)


def _ensure_profile(db: Session, profile_id: UUID) -> Profile:
    """
    Ensures that a profile exists for the given ID.

    Raises:
        HTTPException: 404 Not Found if profile does not exist.
    """
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return prof


def _ensure_content(db: Session, content_id: UUID) -> Content:
    """
    Ensures that a content item exists for the given ID.

    Raises:
        HTTPException: 404 Not Found if content does not exist.
    """
    cnt = db.get(Content, content_id)
    if not cnt:
        raise HTTPException(status_code=404, detail="Content not found")
    return cnt


def _ensure_episode(db: Session, episode_id: Optional[UUID]) -> Optional[Episode]:
    """
    Ensures that an episode exists for the given ID, if provided.

    Raises:
        HTTPException: 404 Not Found if episode ID is provided but episode does not exist.
    """
    if episode_id is None:
        return None
    ep = db.get(Episode, episode_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    return ep


def _ensure_episode_matches_content(ep: Episode, content_id: UUID) -> None:
    """
    Checks if an episode belongs to the specified content.

    Raises:
        HTTPException: 409 Conflict if the episode content_id does not match the provided content_id.
    """
    if getattr(ep, "content_id", None) != content_id:
        raise HTTPException(
            status_code=409, detail="Episode does not belong to given content"
        )


def _profile_belongs_to_user(profile: Profile, user_id: UUID) -> None:
    """
    Checks if a profile belongs to the specified user.

    Raises:
        HTTPException: 403 Forbidden if the profile user_id does not match the provided user_id.
    """
    if profile.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Profile does not belong to current user"
        )


def _normalize_progress_and_completion(
    entity: Playback,
    upd_progress: Optional[int],
    upd_completed: Optional[bool],
    upd_ended_at: Optional[datetime],
) -> None:
    """
    Normalizes progress, completed status, and ended_at timestamp based on update rules.

    Raises:
        HTTPException: 400 Bad Request if progress_seconds is negative.
    """
    if upd_progress is not None:
        if upd_progress < 0:
            raise HTTPException(status_code=400, detail="progress_seconds must be >= 0")
        entity.progress_seconds = upd_progress

    if upd_completed is not None:
        entity.completed = upd_completed
        if upd_completed and entity.ended_at is None and upd_ended_at is None:
            entity.ended_at = datetime.now(timezone.utc)

    if upd_ended_at is not None:
        entity.ended_at = upd_ended_at
        if upd_ended_at and not entity.completed:
            entity.completed = True


@router.get("", response_model=List[PlaybackListItem])
def list_playbacks(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    profile_id: Optional[UUID] = Query(None),
    content_id: Optional[UUID] = Query(None),
    episode_id: Optional[UUID] = Query(None),
    completed: Optional[bool] = Query(None),
    device_q: Optional[str] = Query(None, description="Filter by device (ilike)"),
    started_from: Optional[datetime] = Query(None),
    started_to: Optional[datetime] = Query(None),
    ended_from: Optional[datetime] = Query(None),
    ended_to: Optional[datetime] = Query(None),
    min_progress: Optional[int] = Query(None, ge=0),
    max_progress: Optional[int] = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[PlaybackListItem]:
    """
    Lists playbacks with filters and pagination (admin only).
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

    q = q.order_by(Playback.started_at.desc(), Playback.created_at.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/{playback_id}", response_model=PlaybackOut)
def get_playback(
    playback_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Playback:
    """
    Retrieves a single playback by ID (admin only).

    Raises:
        HTTPException: 404 Not Found if playback does not exist.
    """
    pb = db.get(Playback, playback_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playback not found")
    return pb


@router.post("", response_model=PlaybackOut, status_code=status.HTTP_201_CREATED)
def create_playback(
    payload: PlaybackCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Playback:
    """
    Creates a playback record (admin only). Validates profile, content, and episode consistency.

    Raises:
        HTTPException: 404 Not Found if profile, content, or episode ID is invalid.
        HTTPException: 409 Conflict if episode does not belong to the content.
        HTTPException: 400 Bad Request if progress_seconds is negative.
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
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        progress_seconds=payload.progress_seconds or 0,
        completed=payload.completed or False,
        device=payload.device,
        created_by=admin.id,
    )
    _normalize_progress_and_completion(
        entity, payload.progress_seconds, payload.completed, payload.ended_at
    )

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
) -> Playback:
    """
    Updates a playback record (admin only). Normalizes progress and completion fields.

    Raises:
        HTTPException: 404 Not Found if playback does not exist.
        HTTPException: 400 Bad Request if progress_seconds is negative.
    """
    pb = db.get(Playback, playback_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playback not found")

    _normalize_progress_and_completion(
        pb, payload.progress_seconds, payload.completed, payload.ended_at
    )

    if payload.device is not None:
        pb.device = payload.device or None

    pb.updated_by = admin.id
    db.commit()
    db.refresh(pb)
    return pb


@router.delete("/{playback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playback(
    playback_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    """
    Deletes a playback record (hard delete, admin only).
    """
    pb = db.get(Playback, playback_id)
    if not pb:
        return None
    db.delete(pb)
    db.commit()
    return None


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
) -> List[PlaybackListItem]:
    """
    Lists playbacks for a specific profile belonging to the authenticated user.

    Raises:
        HTTPException: 404 Not Found if profile does not exist.
        HTTPException: 403 Forbidden if the profile does not belong to the current user.
    """
    prof = _ensure_profile(db, profile_id)
    _profile_belongs_to_user(prof, me.id)

    q = db.query(Playback).filter(Playback.profile_id == profile_id)
    if content_id:
        q = q.filter(Playback.content_id == content_id)
    if episode_id:
        q = q.filter(Playback.episode_id == episode_id)
    if completed is not None:
        q = q.filter(Playback.completed.is_(completed))

    q = q.order_by(Playback.started_at.desc(), Playback.created_at.desc())
    return q.limit(limit).offset(offset).all()


@me_router.post("", response_model=PlaybackOut, status_code=status.HTTP_201_CREATED)
def start_playback_for_my_profile(
    profile_id: UUID,
    payload: PlaybackCreate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Playback:
    """
    Starts a new playback for a profile belonging to the authenticated user.

    Raises:
        HTTPException: 404 Not Found if profile or content is invalid.
        HTTPException: 403 Forbidden if the profile does not belong to the current user.
        HTTPException: 400 Bad Request if profile_id in payload doesn't match route parameter.
        HTTPException: 409 Conflict if episode does not belong to the content.
        HTTPException: 400 Bad Request if progress_seconds is negative.
    """
    prof = _ensure_profile(db, profile_id)
    _profile_belongs_to_user(prof, me.id)

    if payload.profile_id != profile_id:
        raise HTTPException(
            status_code=400, detail="profile_id mismatch with route parameter"
        )

    cnt = _ensure_content(db, payload.content_id)
    ep = _ensure_episode(db, payload.episode_id)
    if ep:
        _ensure_episode_matches_content(ep, cnt.id)

    entity = Playback(
        profile_id=profile_id,
        content_id=cnt.id,
        episode_id=getattr(ep, "id", None),
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        progress_seconds=payload.progress_seconds or 0,
        completed=payload.completed or False,
        device=payload.device,
        created_by=me.id,
    )
    _normalize_progress_and_completion(
        entity, payload.progress_seconds, payload.completed, payload.ended_at
    )

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
) -> Playback:
    """
    Updates an existing playback record for a profile belonging to the authenticated user.

    Raises:
        HTTPException: 404 Not Found if profile or playback does not exist, or if playback doesn't belong to the profile.
        HTTPException: 403 Forbidden if the profile does not belong to the current user.
        HTTPException: 400 Bad Request if progress_seconds is negative.
    """
    prof = _ensure_profile(db, profile_id)
    _profile_belongs_to_user(prof, me.id)

    pb = db.get(Playback, playback_id)
    if not pb or pb.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Playback not found")

    _normalize_progress_and_completion(
        pb, payload.progress_seconds, payload.completed, payload.ended_at
    )

    if payload.device is not None:
        pb.device = payload.device or None

    pb.updated_by = me.id
    db.commit()
    db.refresh(pb)
    return pb


@me_router.post("/{playback_id}/finish", response_model=PlaybackOut)
def finish_my_profile_playback(
    profile_id: UUID,
    playback_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Playback:
    """
    Marks a playback as completed (completed=True, sets ended_at to now if missing) for a profile belonging to the authenticated user.

    Raises:
        HTTPException: 404 Not Found if profile or playback does not exist, or if playback doesn't belong to the profile.
        HTTPException: 403 Forbidden if the profile does not belong to the current user.
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

    pb.updated_by = me.id
    db.commit()
    db.refresh(pb)
    return pb


@me_router.delete("/{playback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_profile_playback(
    profile_id: UUID,
    playback_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> None:
    """
    Deletes a playback record for a profile belonging to the authenticated user.

    Raises:
        HTTPException: 404 Not Found if profile does not exist.
        HTTPException: 403 Forbidden if the profile does not belong to the current user.
    """
    prof = _ensure_profile(db, profile_id)
    _profile_belongs_to_user(prof, me.id)

    pb = db.get(Playback, playback_id)
    if not pb or pb.profile_id != profile_id:
        return None

    db.delete(pb)
    db.commit()
    return None
