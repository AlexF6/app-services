# app/api/v1/me_watchlist.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
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

router = APIRouter(prefix="/me/watchlist", tags=["My Watchlist"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile_belongs_to_user(db: Session, profile_id: UUID, user_id: UUID) -> bool:
    prof = db.get(Profile, profile_id)
    return prof is not None and prof.user_id == user_id


def _ensure_profile_of_user(db: Session, profile_id: UUID, user_id: UUID) -> None:
    """
    Ensures the profile exists and belongs to the current user. Raises 404/403 accordingly.
    """
    prof = db.get(Profile, profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    if prof.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: profile not owned by user")


def _ensure_content_exists(db: Session, content_id: UUID) -> None:
    if not db.get(Content, content_id):
        raise HTTPException(status_code=404, detail="Content not found")


def _exists_watchlist_item(db: Session, profile_id: UUID, content_id: UUID) -> bool:
    return (
        db.query(Watchlist)
        .filter(Watchlist.profile_id == profile_id, Watchlist.content_id == content_id)
        .first()
        is not None
    )


def _ensure_watchlist_item_of_user(db: Session, watchlist_id: UUID, user_id: UUID) -> Watchlist:
    """
    Fetches watchlist item and ensures its profile belongs to the current user.
    """
    entity = db.get(Watchlist, watchlist_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    if not _profile_belongs_to_user(db, entity.profile_id, user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return entity


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[WatchlistListItem])
def list_my_watchlist_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    profile_id: Optional[UUID] = Query(None, description="Filter by a specific profile you own"),
    content_id: Optional[UUID] = Query(None),
    added_from: Optional[datetime] = Query(None),
    added_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[WatchlistListItem]:
    """
    Lists your watchlist items. If `profile_id` is omitted, returns items from ALL your profiles.
    """
    q = db.query(Watchlist).join(Profile, Profile.id == Watchlist.profile_id)

    # Scope to current user's profiles
    q = q.filter(Profile.user_id == current_user.id)

    if profile_id:
        # Ensure the provided profile belongs to the user
        _ensure_profile_of_user(db, profile_id, current_user.id)
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
def get_my_watchlist_item(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Watchlist:
    """
    Retrieves a single watchlist item by ID, only if it belongs to one of your profiles.
    """
    entity = _ensure_watchlist_item_of_user(db, watchlist_id, current_user.id)
    return entity


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def create_my_watchlist_item(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Watchlist:
    """
    Adds content to your watchlist (for a profile you own). Prevents duplicates.
    """
    _ensure_profile_of_user(db, payload.profile_id, current_user.id)
    _ensure_content_exists(db, payload.content_id)

    if _exists_watchlist_item(db, payload.profile_id, payload.content_id):
        raise HTTPException(status_code=409, detail="Item already exists in watchlist")

    entity = Watchlist(
        profile_id=payload.profile_id,
        content_id=payload.content_id,
        created_by=current_user.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/{watchlist_id}", response_model=WatchlistOut)
def update_my_watchlist_item(
    watchlist_id: UUID,
    payload: WatchlistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Watchlist:
    """
    Updates your watchlist item. You can move it to another of your profiles and/or change content.
    Prevents duplicates and ensures new profile (if provided) belongs to you.
    """
    entity = _ensure_watchlist_item_of_user(db, watchlist_id, current_user.id)

    new_profile_id = payload.profile_id or entity.profile_id
    new_content_id = payload.content_id or entity.content_id

    # Validate new targets
    _ensure_profile_of_user(db, new_profile_id, current_user.id)
    _ensure_content_exists(db, new_content_id)

    # Check for duplicate only if the pair changes
    if (new_profile_id != entity.profile_id) or (new_content_id != entity.content_id):
        if _exists_watchlist_item(db, new_profile_id, new_content_id):
            raise HTTPException(status_code=409, detail="Item already exists in watchlist")
        entity.profile_id = new_profile_id
        entity.content_id = new_content_id

    entity.updated_by = current_user.id
    db.commit()
    db.refresh(entity)
    return entity


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_watchlist_item(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Deletes a watchlist item you own.
    """
    entity = _ensure_watchlist_item_of_user(db, watchlist_id, current_user.id)
    db.delete(entity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_watchlist_item_by_pair(
    profile_id: UUID = Query(...),
    content_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Convenience deletion using (profile_id, content_id).
    Only works for your own profile.
    """
    _ensure_profile_of_user(db, profile_id, current_user.id)

    entity = (
        db.query(Watchlist)
        .filter(Watchlist.profile_id == profile_id, Watchlist.content_id == content_id)
        .first()
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    db.delete(entity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
