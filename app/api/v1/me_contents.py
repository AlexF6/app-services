from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.content import Content
from app.models.auditmixin import ContentType
from app.schemas.content import ContentListItem, ContentOut

router = APIRouter(prefix="/me/contents", tags=["My Contents"])

@router.get("", response_model=List[ContentListItem])
def list_my_contents(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    q: Optional[str] = Query(None, description="Search by title or description (ilike)"),
    type_q: Optional[ContentType] = Query(None, description="Filter by content type"),
    genre_q: Optional[str] = Query(None, description="Genre fragment (ilike)"),
    year_from: Optional[int] = Query(None, ge=1800, le=2100),
    year_to: Optional[int] = Query(None, ge=1800, le=2100),
    order_by: str = Query("created_at", regex="^(title|release_year|created_at)$"),
    order_dir: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(24, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[ContentListItem]:
    qset = db.query(
        Content.id,
        Content.title,
        Content.type,
        Content.release_year,
        Content.age_rating,
        Content.genres,
        Content.duration_minutes,
        Content.thumbnail,
        Content.created_at,
    )

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

    sort_col = {
        "title": Content.title,
        "release_year": Content.release_year,
        "created_at": Content.created_at,
    }[order_by]
    qset = qset.order_by(sort_col.asc() if order_dir == "asc" else sort_col.desc())

    rows = qset.limit(limit).offset(offset).all()
    return [
        ContentListItem.model_validate(
            {
                "id": r.id,
                "title": r.title,
                "type": r.type,
                "release_year": r.release_year,
                "age_rating": r.age_rating,
                "genres": r.genres,
                "duration_minutes": r.duration_minutes,
                "thumbnail": r.thumbnail,
            }
        )
        for r in rows
    ]


@router.get("/{content_id}", response_model=ContentOut)
def get_my_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ContentOut:
    entity = db.get(Content, content_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Content not found")
    return entity
