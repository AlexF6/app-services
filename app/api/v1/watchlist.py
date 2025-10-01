from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin
from app.api.v1.auth import get_current_user

from app.models.user import User
from app.models.profile import Profile
from app.models.content import Content
from app.models.watchlist import Watchlist

from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistUpdate,
    WatchlistOut,
    WatchlistListItem,
)

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


def _ensure_profile_and_content(
    db: Session, profile_id: UUID, content_id: UUID
) -> None:
    """
    Checks if the given Profile and Content IDs exist in the database.

    Raises:
        HTTPException: 404 Not Found if either Profile or Content is missing.
    """
    if not db.get(Profile, profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    if not db.get(Content, content_id):
        raise HTTPException(status_code=404, detail="Content not found")


def _ensure_profile_belongs_to_user(
    db: Session, profile_id: UUID, user_id: UUID
) -> Profile:
    """
    Retrieves a profile and ensures it belongs to the specified user ID.

    Raises:
        HTTPException: 404 Not Found if profile does not exist.
        HTTPException: 403 Forbidden if profile does not belong to the user.
    """
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    if prof.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Profile does not belong to current user"
        )
    return prof


def _exists_watchlist_item(db: Session, profile_id: UUID, content_id: UUID) -> bool:
    """
    Checks for the existence of a Watchlist item with the given profile and content IDs.
    """
    return (
        db.query(Watchlist)
        .filter(Watchlist.profile_id == profile_id, Watchlist.content_id == content_id)
        .first()
        is not None
    )


@router.get("", response_model=List[WatchlistListItem])
def list_watchlist_items(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    profile_id: Optional[UUID] = Query(None),
    content_id: Optional[UUID] = Query(None),
    added_from: Optional[datetime] = Query(None),
    added_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[WatchlistListItem]:
    """
    Lists watchlist items with filters (admin only).
    """
    q = db.query(Watchlist)

    if profile_id:
        q = q.filter(Watchlist.profile_id == profile_id)
    if content_id:
        q = q.filter(Watchlist.content_id == content_id)
    if added_from:
        q = q.filter(Watchlist.added_at >= added_from)
    if added_to:
        q = q.filter(Watchlist.added_at <= added_to)

    q = q.order_by(Watchlist.added_at.desc(), Watchlist.created_at.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/{watchlist_id}", response_model=WatchlistOut)
def get_watchlist_item(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Watchlist:
    """
    Retrieves a single watchlist item by ID (admin only).

    Raises:
        HTTPException: 404 Not Found if item does not exist.
    """
    item = db.get(Watchlist, watchlist_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def create_watchlist_item(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Watchlist:
    """
    Creates a watchlist item (admin only). Avoids duplicates by profile_id and content_id.

    Raises:
        HTTPException: 404 Not Found if Profile or Content is invalid.
        HTTPException: 409 Conflict if the item already exists in the watchlist.
    """
    _ensure_profile_and_content(db, payload.profile_id, payload.content_id)

    if _exists_watchlist_item(db, payload.profile_id, payload.content_id):
        raise HTTPException(status_code=409, detail="Item already exists in watchlist")

    entity = Watchlist(
        profile_id=payload.profile_id,
        content_id=payload.content_id,
        created_by=admin.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/{watchlist_id}", response_model=WatchlistOut)
def update_watchlist_item(
    watchlist_id: UUID,
    payload: WatchlistUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Watchlist:
    """
    Updates a watchlist item (admin only). Validates profile/content existence and duplicate combination.

    Raises:
        HTTPException: 404 Not Found if item, Profile, or Content is invalid.
        HTTPException: 409 Conflict if the update results in a duplicate item (same profile_id + content_id).
    """
    entity = db.get(Watchlist, watchlist_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    new_profile_id = payload.profile_id or entity.profile_id
    new_content_id = payload.content_id or entity.content_id

    _ensure_profile_and_content(db, new_profile_id, new_content_id)

    # Check for duplicate if the combination is changing
    if (new_profile_id != entity.profile_id) or (new_content_id != entity.content_id):
        if _exists_watchlist_item(db, new_profile_id, new_content_id):
            raise HTTPException(
                status_code=409, detail="Item already exists in watchlist"
            )
        entity.profile_id = new_profile_id
        entity.content_id = new_content_id

    entity.updated_by = admin.id
    db.commit()
    db.refresh(entity)
    return entity


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    """
    Deletes a watchlist item (admin only).
    """
    entity = db.get(Watchlist, watchlist_id)
    if not entity:
        return None
    db.delete(entity)
    db.commit()
    return None


profile_router = APIRouter(
    prefix="/profiles/{profile_id}/watchlist", tags=["Watchlist (My Profile)"]
)


class WatchlistQuickAdd(BaseModel):
    content_id: UUID


@profile_router.get("", response_model=List[WatchlistListItem])
def my_profile_watchlist(
    profile_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    q_title: Optional[str] = Query(None, description="Search by content title (ilike)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[WatchlistListItem]:
    """
    Lists the watchlist for the authenticated user's profile.

    Raises:
        HTTPException: 404 Not Found if profile does not exist.
        HTTPException: 403 Forbidden if profile doesn't belong to the user.
    """
    _ensure_profile_belongs_to_user(db, profile_id, me.id)

    q = db.query(Watchlist).filter(Watchlist.profile_id == profile_id)

    if q_title:
        like = f"%{q_title.lower()}%"
        # Join is necessary to filter by Content's title
        q = q.join(Content, Content.id == Watchlist.content_id).filter(
            func.lower(Content.title).ilike(like)
        )

    q = q.order_by(Watchlist.added_at.desc(), Watchlist.created_at.desc())
    return q.limit(limit).offset(offset).all()


@profile_router.post(
    "", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED
)
def add_to_my_profile_watchlist(
    profile_id: UUID,
    payload: WatchlistQuickAdd,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Watchlist:
    """
    Adds content to the authenticated user's profile watchlist. Idempotent: returns 409 if already exists.

    Raises:
        HTTPException: 404 Not Found if Profile or Content is invalid.
        HTTPException: 403 Forbidden if profile doesn't belong to the user.
        HTTPException: 409 Conflict if the item already exists in the watchlist.
    """
    _ensure_profile_belongs_to_user(db, profile_id, me.id)

    _ensure_profile_and_content(db, profile_id, payload.content_id)

    if _exists_watchlist_item(db, profile_id, payload.content_id):
        raise HTTPException(status_code=409, detail="Item already exists in watchlist")

    entity = Watchlist(
        profile_id=profile_id,
        content_id=payload.content_id,
        created_by=me.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@profile_router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_my_profile_watchlist(
    profile_id: UUID,
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> None:
    """
    Removes a watchlist item by its ID from the authenticated user's profile watchlist.

    Raises:
        HTTPException: 404 Not Found if profile does not exist.
        HTTPException: 403 Forbidden if profile doesn't belong to the user.
    """
    _ensure_profile_belongs_to_user(db, profile_id, me.id)

    entity = db.get(Watchlist, watchlist_id)
    # Check if item exists and belongs to the profile
    if not entity or entity.profile_id != profile_id:
        return None

    db.delete(entity)
    db.commit()
    return None


@profile_router.delete(
    "/by-content/{content_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_by_content_from_my_profile_watchlist(
    profile_id: UUID,
    content_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> None:
    """
    Removes a watchlist item by content_id from the authenticated user's profile watchlist (convenience endpoint). Does not fail if the item doesn't exist.

    Raises:
        HTTPException: 404 Not Found if profile does not exist.
        HTTPException: 403 Forbidden if profile doesn't belong to the user.
    """
    _ensure_profile_belongs_to_user(db, profile_id, me.id)

    entity = (
        db.query(Watchlist)
        .filter(Watchlist.profile_id == profile_id, Watchlist.content_id == content_id)
        .first()
    )
    if not entity:
        return None

    db.delete(entity)
    db.commit()
    return None
