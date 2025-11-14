from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.auth import get_current_user

from app.models.content import Content
from app.models.episode import Episode
from app.models.user import User
from app.schemas.episode import EpisodeOut, EpisodeListItem

router = APIRouter(prefix="/me/episodes", tags=["My Episodes"])
content_router = APIRouter(
    prefix="/me/contents/{content_id}/episodes", tags=["My Episodes (By Content)"]
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_content(db: Session, content_id: UUID) -> Content:
    c = db.get(Content, content_id)
    if not c:
        raise HTTPException(status_code=404, detail="Content not found")
    return c


def _to_episode_out(e: Episode, include_video: bool) -> EpisodeOut:
    out = EpisodeOut.model_validate(e, from_attributes=True)
    if not include_video:
        out.video_url = None
    return out


# ---------------------------------------------------------------------------
# Endpoints (READ-ONLY for authenticated users)
# ---------------------------------------------------------------------------

@router.get("", response_model=List[EpisodeListItem])
def list_my_episodes(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    content_id: Optional[UUID] = Query(None),
    season: Optional[int] = Query(None, ge=1),
    ep: Optional[int] = Query(None, ge=1, description="Exact episode_number"),
    q_title: Optional[str] = Query(None, description="Search by title (ilike)"),
    min_duration: Optional[int] = Query(None, ge=1, description="Min duration in seconds"),
    max_duration: Optional[int] = Query(None, ge=1, description="Max duration in seconds"),
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
    Lists episodes visible to the current user (read-only).
    Durations are in **seconds**.
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
        q = q.filter(Episode.duration_seconds >= min_duration)
    if max_duration is not None:
        q = q.filter(Episode.duration_seconds <= max_duration)
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
def get_my_episode(
    episode_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    include_video: bool = Query(False, description="Include video_url in response"),
) -> EpisodeOut:
    e = db.get(Episode, episode_id)
    if not e:
        raise HTTPException(status_code=404, detail="Episode not found")
    return _to_episode_out(e, include_video)


@content_router.get("", response_model=List[EpisodeListItem])
def list_my_episodes_by_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    season: Optional[int] = Query(None, ge=1),
    q_title: Optional[str] = Query(None),
    order_by: str = Query(
        "episode", pattern="^(season|episode|title|release_date|created_at)$"
    ),
    order_dir: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[EpisodeListItem]:
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
