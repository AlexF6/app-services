from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin
from app.models.content import Content
from app.models.auditmixin import ContentType
from app.models.user import User
from app.schemas.content import (
    ContentCreate,
    ContentUpdate,
    ContentOut,
    ContentListItem,
)

router = APIRouter(prefix="/contents", tags=["Contents"])


@router.get("", response_model=List[ContentListItem])
def list_contents(
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
    q: Optional[str] = Query(
        None, description="Search by title or description (ilike)"
    ),
    type_q: Optional[ContentType] = Query(None, description="Filter by content type"),
    genre_q: Optional[str] = Query(None, description="Genre fragment (ilike)"),
    year_from: Optional[int] = Query(None, ge=1800, le=2100),
    year_to: Optional[int] = Query(None, ge=1800, le=2100),
    min_duration: Optional[int] = Query(None, ge=1),
    max_duration: Optional[int] = Query(None, ge=1),
    age_rating: Optional[str] = Query(None, max_length=10),
    order_by: str = Query("created_at", pattern="^(title|release_year|created_at)$"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[ContentListItem]:
    """
    Lists contents with filters and pagination (admin only for now).
    """
    qset = db.query(Content)

    if q:
        like = f"%{q.lower()}%"
        qset = qset.filter(
            func.lower(Content.title).ilike(like)
            | func.lower(Content.description).ilike(like)
        )
    if type_q:
        qset = qset.filter(Content.type == type_q)
    if genre_q:
        qset = qset.filter(func.lower(Content.genres).ilike(f"%{genre_q.lower()}%"))
    if year_from is not None:
        qset = qset.filter(Content.release_year >= year_from)
    if year_to is not None:
        qset = qset.filter(Content.release_year <= year_to)
    if min_duration is not None:
        qset = qset.filter(Content.duration_minutes >= min_duration)
    if max_duration is not None:
        qset = qset.filter(Content.duration_minutes <= max_duration)
    if age_rating:
        qset = qset.filter(Content.age_rating == age_rating)

    col = {
        "title": Content.title,
        "release_year": Content.release_year,
        "created_at": Content.created_at,
    }[order_by]
    qset = qset.order_by(col.asc() if order_dir == "asc" else col.desc())

    return qset.limit(limit).offset(offset).all()


@router.get("/{content_id}", response_model=ContentOut)
def get_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
) -> Content:
    """
    Retrieves a single content item by its ID (admin only for now).

    Raises:
        HTTPException: 404 Not Found if content does not exist.
    """
    entity = db.get(Content, content_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Content not found")
    return entity


@router.post("", response_model=ContentOut, status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreate,
    db: Session = Depends(get_db),
    admin: "User" = Depends(require_admin),
) -> Content:
    """
    Creates a new content item. Performs an optional check for title + year uniqueness (admin only).

    Raises:
        HTTPException: 409 Conflict if content with the same title and year already exists.
    """
    if payload.release_year is not None:
        exists = (
            db.query(Content)
            .filter(
                func.lower(Content.title) == payload.title.lower(),
                Content.release_year == payload.release_year,
            )
            .first()
        )
        if exists:
            raise HTTPException(
                status_code=409,
                detail="Content with same title and year already exists",
            )

    entity = Content(
        title=payload.title,
        type=payload.type,
        description=payload.description,
        release_year=payload.release_year,
        duration_minutes=payload.duration_minutes,
        age_rating=payload.age_rating,
        genres=payload.genres,
        created_by=admin.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/{content_id}", response_model=ContentOut)
def update_content(
    content_id: UUID,
    payload: ContentUpdate,
    db: Session = Depends(get_db),
    admin: "User" = Depends(require_admin),
) -> Content:
    """
    Updates an existing content item. Performs an optional check for title + year uniqueness if they are modified (admin only).

    Raises:
        HTTPException: 404 Not Found if content does not exist.
        HTTPException: 409 Conflict if the update would violate the title + year uniqueness rule.
    """
    entity = db.get(Content, content_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Content not found")

    maybe_title = payload.title if payload.title is not None else entity.title
    maybe_year = (
        payload.release_year
        if payload.release_year is not None
        else entity.release_year
    )
    if maybe_title != entity.title or maybe_year != entity.release_year:
        if maybe_year is not None:
            conflict = (
                db.query(Content)
                .filter(
                    func.lower(Content.title) == maybe_title.lower(),
                    Content.release_year == maybe_year,
                    Content.id != entity.id,
                )
                .first()
            )
            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail="Content with same title and year already exists",
                )

    if payload.title is not None:
        entity.title = payload.title
    if payload.type is not None:
        entity.type = payload.type
    if payload.description is not None:
        entity.description = payload.description
    if payload.release_year is not None:
        entity.release_year = payload.release_year
    if payload.duration_minutes is not None:
        entity.duration_minutes = payload.duration_minutes
    if payload.age_rating is not None:
        entity.age_rating = payload.age_rating
    if payload.genres is not None:
        entity.genres = payload.genres

    entity.updated_by = admin.id
    db.commit()
    db.refresh(entity)
    return entity


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    _: "User" = Depends(require_admin),
) -> Response:
    """
    Deletes a content item (hard delete). May raise IntegrityError if existing foreign keys prevent deletion.

    Raises:
        HTTPException: 409 Conflict if deletion is prevented by existing foreign key constraints.
    """
    entity = db.get(Content, content_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    try:
        db.delete(entity)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete content due to existing references (episodes/playbacks/watchlists)",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
