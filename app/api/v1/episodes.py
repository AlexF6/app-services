from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin
from app.models.content import Content
from app.models.episode import Episode
from app.models.user import User
from app.schemas.episode import (
    EpisodeCreate,
    EpisodeUpdate,
    EpisodeOut,
    EpisodeListItem,
)

router = APIRouter(prefix="/episodes", tags=["Episodes"])
content_router = APIRouter(
    prefix="/contents/{content_id}/episodes", tags=["Episodes (By Content)"]
)


def _ensure_content(db: Session, content_id: UUID) -> Content:
    """
    Ensures that a content item exists for the given ID.

    Raises:
        HTTPException: 404 Not Found if content does not exist.
    """
    c = db.get(Content, content_id)
    if not c:
        raise HTTPException(status_code=404, detail="Content not found")
    return c


def _exists_number_for_content(
    db: Session,
    content_id: UUID,
    season_number: int,
    episode_number: int,
    exclude_id: Optional[UUID] = None,
) -> bool:
    """
    Checks if an episode with the given season and episode number already exists
    for the specified content ID, optionally excluding a specific episode ID.
    """
    q = db.query(Episode).filter(
        Episode.content_id == content_id,
        Episode.season_number == season_number,
        Episode.episode_number == episode_number,
    )
    if exclude_id:
        q = q.filter(Episode.id != exclude_id)
    return db.query(q.exists()).scalar()


@router.get("", response_model=List[EpisodeListItem])
def list_episodes(
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
    content_id: Optional[UUID] = Query(None),
    season: Optional[int] = Query(None, ge=1),
    ep: Optional[int] = Query(None, ge=1, description="Exact episode_number"),
    q_title: Optional[str] = Query(None, description="Search by title (ilike)"),
    min_duration: Optional[int] = Query(None, ge=1),
    max_duration: Optional[int] = Query(None, ge=1),
    year_from: Optional[int] = Query(None, ge=1800, le=2100),
    year_to: Optional[int] = Query(None, ge=1800, le=2100),
    order_by: str = Query(
        "created_at", pattern="^(season|episode|title|created_at|release_date)$"
    ),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[EpisodeListItem]:
    """
    Lists episodes with filters and pagination (admin only).
    """
    q = db.query(Episode)

    if content_id:
        q = q.filter(Episode.content_id == content_id)
    if season:
        q = q.filter(Episode.season_number == season)
    if ep:
        q = q.filter(Episode.episode_number == ep)
    if q_title:
        like = f"%{q_title.lower()}%"
        q = q.filter(func.lower(Episode.title).ilike(like))
    if min_duration is not None:
        q = q.filter(Episode.duration_minutes >= min_duration)
    if max_duration is not None:
        q = q.filter(Episode.duration_minutes <= max_duration)
    if year_from is not None:
        q = q.filter(Episode.release_date >= f"{year_from}-01-01")
    if year_to is not None:
        q = q.filter(Episode.release_date <= f"{year_to}-12-31")

    colmap = {
        "season": Episode.season_number,
        "episode": Episode.episode_number,
        "title": Episode.title,
        "created_at": Episode.created_at,
        "release_date": Episode.release_date,
    }
    q = q.order_by(
        colmap[order_by].asc() if order_dir == "asc" else colmap[order_by].desc()
    )

    return q.limit(limit).offset(offset).all()


@router.get("/{episode_id}", response_model=EpisodeOut)
def get_episode(
    episode_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
) -> Episode:
    """
    Retrieves a single episode by its ID (admin only).

    Raises:
        HTTPException: 404 Not Found if episode does not exist.
    """
    e = db.get(Episode, episode_id)
    if not e:
        raise HTTPException(status_code=404, detail="Episode not found")
    return e


@router.post("", response_model=EpisodeOut, status_code=status.HTTP_201_CREATED)
def create_episode(
    payload: EpisodeCreate,
    db: Session = Depends(get_db),
    admin: "User" = Depends(require_admin),
) -> Episode:
    """
    Creates an episode for a content item. Enforces optional uniqueness for (content_id, season_number, episode_number) (admin only).

    Raises:
        HTTPException: 404 Not Found if the content ID is invalid.
        HTTPException: 409 Conflict if episode number already exists for that content/season.
    """
    _ensure_content(db, payload.content_id)

    if _exists_number_for_content(
        db, payload.content_id, payload.season_number, payload.episode_number
    ):
        raise HTTPException(
            status_code=409,
            detail="Episode number already exists for this content/season",
        )

    entity = Episode(
        content_id=payload.content_id,
        season_number=payload.season_number,
        episode_number=payload.episode_number,
        title=payload.title,
        duration_minutes=payload.duration_minutes,
        release_date=payload.release_date,
        created_by=admin.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: UUID,
    payload: EpisodeUpdate,
    db: Session = Depends(get_db),
    admin: "User" = Depends(require_admin),
) -> Episode:
    """
    Updates an existing episode. Validates uniqueness if season or episode number is modified (admin only).

    Raises:
        HTTPException: 404 Not Found if episode does not exist.
        HTTPException: 409 Conflict if the update would violate the season/episode number uniqueness.
    """
    e = db.get(Episode, episode_id)
    if not e:
        raise HTTPException(status_code=404, detail="Episode not found")

    new_season = (
        payload.season_number if payload.season_number is not None else e.season_number
    )
    new_episode = (
        payload.episode_number
        if payload.episode_number is not None
        else e.episode_number
    )

    if new_season != e.season_number or new_episode != e.episode_number:
        if _exists_number_for_content(
            db, e.content_id, new_season, new_episode, exclude_id=e.id
        ):
            raise HTTPException(
                status_code=409,
                detail="Episode number already exists for this content/season",
            )

    if payload.season_number is not None:
        e.season_number = payload.season_number
    if payload.episode_number is not None:
        e.episode_number = payload.episode_number
    if payload.title is not None:
        e.title = payload.title
    if payload.duration_minutes is not None:
        e.duration_minutes = payload.duration_minutes
    if payload.release_date is not None:
        e.release_date = payload.release_date

    e.updated_by = admin.id
    db.commit()
    db.refresh(e)
    return e


@router.delete("/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(
    episode_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
) -> Response:
    """
    Deletes an episode (admin only).
    """
    e = db.get(Episode, episode_id)
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    db.delete(e)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@content_router.get("", response_model=List[EpisodeListItem])
def list_episodes_by_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
    season: Optional[int] = Query(None, ge=1),
    q_title: Optional[str] = Query(None),
    order_by: str = Query(
        "episode", pattern="^(season|episode|title|release_date|created_at)$"
    ),
    order_dir: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[EpisodeListItem]:
    """
    Lists episodes belonging to a specific content item, with filtering and ordering (admin only).

    Raises:
        HTTPException: 404 Not Found if the content ID is invalid.
    """
    _ensure_content(db, content_id)

    q = db.query(Episode).filter(Episode.content_id == content_id)
    if season:
        q = q.filter(Episode.season_number == season)
    if q_title:
        like = f"%{q_title.lower()}%"
        q = q.filter(func.lower(Episode.title).ilike(like))

    col = {
        "season": Episode.season_number,
        "episode": Episode.episode_number,
        "title": Episode.title,
        "release_date": Episode.release_date,
        "created_at": Episode.created_at,
    }[order_by]
    q = q.order_by(col.asc() if order_dir == "asc" else col.desc())

    return q.limit(limit).offset(offset).all()


@content_router.post("", response_model=EpisodeOut, status_code=status.HTTP_201_CREATED)
def create_episode_for_content(
    content_id: UUID,
    payload: EpisodeUpdate,
    db: Session = Depends(get_db),
    admin: "User" = Depends(require_admin),
) -> Episode:
    """
    Creates an episode linked to the `content_id` in the route path.
    Requires: title, season_number, episode_number (via EpisodeUpdate for convenience) (admin only).

    Raises:
        HTTPException: 404 Not Found if the content ID is invalid.
        HTTPException: 400 Bad Request if required fields are missing.
        HTTPException: 409 Conflict if episode number already exists for that content/season.
    """
    _ensure_content(db, content_id)

    if not payload.title or not payload.season_number or not payload.episode_number:
        raise HTTPException(
            status_code=400,
            detail="title, season_number and episode_number are required",
        )

    if _exists_number_for_content(
        db, content_id, payload.season_number, payload.episode_number
    ):
        raise HTTPException(
            status_code=409,
            detail="Episode number already exists for this content/season",
        )

    entity = Episode(
        content_id=content_id,
        season_number=payload.season_number,
        episode_number=payload.episode_number,
        title=payload.title,
        duration_minutes=payload.duration_minutes,
        release_date=payload.release_date,
        created_by=admin.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity
