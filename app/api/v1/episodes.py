from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin
# from app.api.v1.auth import get_current_user  # si luego necesitas endpoints públicos

from app.models.content import Content
from app.models.episode import Episode
from app.schemas.episode import (
    EpisodeCreate,
    EpisodeUpdate,
    EpisodeOut,
    EpisodeListItem,
)

router = APIRouter(prefix="/episodes", tags=["Episodes"])
content_router = APIRouter(prefix="/contents/{content_id}/episodes", tags=["Episodes (By Content)"])


# ----------------------------
# Helpers
# ----------------------------
def _ensure_content(db: Session, content_id: UUID) -> Content:
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
    q = db.query(Episode).filter(
        Episode.content_id == content_id,
        Episode.season_number == season_number,
        Episode.episode_number == episode_number,
    )
    if exclude_id:
        q = q.filter(Episode.id != exclude_id)
    return db.query(q.exists()).scalar()


# ============================================================
#                           ADMIN
# ============================================================

@router.get("", response_model=List[EpisodeListItem])
def list_episodes(
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
    content_id: Optional[UUID] = Query(None),
    season: Optional[int] = Query(None, ge=1),
    ep: Optional[int] = Query(None, ge=1, description="episode_number exacto"),
    q_title: Optional[str] = Query(None, description="Buscar por título (ilike)"),
    min_duration: Optional[int] = Query(None, ge=1),
    max_duration: Optional[int] = Query(None, ge=1),
    year_from: Optional[int] = Query(None, ge=1800, le=2100),
    year_to: Optional[int] = Query(None, ge=1800, le=2100),
    order_by: str = Query("fecha_creacion", pattern="^(season|episode|title|fecha_creacion|release_date)$"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Lista episodios con filtros y paginación (solo admin).
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
        "fecha_creacion": Episode.fecha_creacion,
        "release_date": Episode.release_date,
    }
    q = q.order_by(colmap[order_by].asc() if order_dir == "asc" else colmap[order_by].desc())

    return q.limit(limit).offset(offset).all()


@router.get("/{episode_id}", response_model=EpisodeOut)
def get_episode(
    episode_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
):
    e = db.get(Episode, episode_id)
    if not e:
        raise HTTPException(status_code=404, detail="Episode not found")
    return e


@router.post("", response_model=EpisodeOut, status_code=status.HTTP_201_CREATED)
def create_episode(
    payload: EpisodeCreate,
    db: Session = Depends(get_db),
    admin: "User" = Depends(require_admin),
):
    """
    Crea un episodio para un contenido. Enforce opcional: (content_id, season_number, episode_number) único.
    """
    _ensure_content(db, payload.content_id)

    if _exists_number_for_content(db, payload.content_id, payload.season_number, payload.episode_number):
        raise HTTPException(status_code=409, detail="Episode number already exists for this content/season")

    entity = Episode(
        content_id=payload.content_id,
        season_number=payload.season_number,
        episode_number=payload.episode_number,
        title=payload.title,
        duration_minutes=payload.duration_minutes,
        release_date=payload.release_date,
        creado_por=admin.id,
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
):
    e = db.get(Episode, episode_id)
    if not e:
        raise HTTPException(status_code=404, detail="Episode not found")

    new_season = payload.season_number if payload.season_number is not None else e.season_number
    new_episode = payload.episode_number if payload.episode_number is not None else e.episode_number

    # Validar unicidad si cambian season/episode
    if new_season != e.season_number or new_episode != e.episode_number:
        if _exists_number_for_content(db, e.content_id, new_season, new_episode, exclude_id=e.id):
            raise HTTPException(status_code=409, detail="Episode number already exists for this content/season")

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

    e.actualizado_por = admin.id
    db.commit()
    db.refresh(e)
    return e


@router.delete("/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(
    episode_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
):
    e = db.get(Episode, episode_id)
    if not e:
        return None
    db.delete(e)
    db.commit()
    return None


# ============================================================
#                 BY CONTENT (scoped a un contenido)
# ============================================================

@content_router.get("", response_model=List[EpisodeListItem])
def list_episodes_by_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
    season: Optional[int] = Query(None, ge=1),
    q_title: Optional[str] = Query(None),
    order_by: str = Query("episode", pattern="^(season|episode|title|release_date|fecha_creacion)$"),
    order_dir: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
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
        "fecha_creacion": Episode.fecha_creacion,
    }[order_by]
    q = q.order_by(col.asc() if order_dir == "asc" else col.desc())

    return q.limit(limit).offset(offset).all()


@content_router.post("", response_model=EpisodeOut, status_code=status.HTTP_201_CREATED)
def create_episode_for_content(
    content_id: UUID,
    payload: EpisodeUpdate,  # reutilizamos campos, pero exigimos title/season/episode
    db: Session = Depends(get_db),
    admin: "User" = Depends(require_admin),
):
    """
    Crear episodio ligado al `content_id` de la ruta.
    Requiere: title, season_number, episode_number (vía EpisodeUpdate aquí por conveniencia).
    """
    _ensure_content(db, content_id)

    # Validaciones mínimas
    if not payload.title or not payload.season_number or not payload.episode_number:
        raise HTTPException(status_code=400, detail="title, season_number and episode_number are required")

    if _exists_number_for_content(db, content_id, payload.season_number, payload.episode_number):
        raise HTTPException(status_code=409, detail="Episode number already exists for this content/season")

    entity = Episode(
        content_id=content_id,
        season_number=payload.season_number,
        episode_number=payload.episode_number,
        title=payload.title,
        duration_minutes=payload.duration_minutes,
        release_date=payload.release_date,
        creado_por=admin.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity
