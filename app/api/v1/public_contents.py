# app/api/v1/public_contents.py
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.auditmixin import ContentType
from app.models.content import Content
from app.schemas.content import ContentOut

router = APIRouter(prefix="/public/contents", tags=["Public Contents"])

@router.get("", response_model=List[ContentOut])
def public_list_contents(
    db: Session = Depends(get_db),
    response: Response = None,
    q: Optional[str] = Query(None, description="Search by title/description (ilike)"),
    type_q: Optional[ContentType] = Query(None),
    genre_q: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None, ge=1800, le=2100),
    year_to: Optional[int] = Query(None, ge=1800, le=2100),
    min_duration_seconds: Optional[int] = Query(None, ge=1),
    max_duration_seconds: Optional[int] = Query(None, ge=1),
    age_rating: Optional[str] = Query(None, max_length=10),
    order_by: str = Query("created_at", pattern="^(title|release_year|created_at)$"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[ContentOut]:
    qset = db.query(Content)

    if q:
        like = f"%{q.lower()}%"
        qset = qset.filter(
            func.lower(Content.title).ilike(like) | func.lower(Content.description).ilike(like)
        )
    if type_q:
        qset = qset.filter(Content.type == type_q)
    if genre_q:
        qset = qset.filter(func.lower(Content.genres).ilike(f"%{genre_q.lower()}%"))
    if year_from is not None:
        qset = qset.filter(Content.release_year >= year_from)
    if year_to is not None:
        qset = qset.filter(Content.release_year <= year_to)
    if min_duration_seconds is not None:
        qset = qset.filter(Content.duration_seconds >= min_duration_seconds)
    if max_duration_seconds is not None:
        qset = qset.filter(Content.duration_seconds <= max_duration_seconds)
    if age_rating:
        qset = qset.filter(Content.age_rating == age_rating)

    col = {
        "title": Content.title,
        "release_year": Content.release_year,
        "created_at": Content.created_at,
    }[order_by]
    qset = qset.order_by(col.asc() if order_dir == "asc" else col.desc())

    rows = qset.limit(limit).offset(offset).all()

    if response is not None:
        response.headers["Cache-Control"] = "public, max-age=60"

    return rows


@router.get("/{content_id}", response_model=ContentOut)
def public_get_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    response: Response = None,
) -> ContentOut:
    entity = db.get(Content, content_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Content not found")

    if response is not None:
        response.headers["Cache-Control"] = "public, max-age=120"

    return entity
