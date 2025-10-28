from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func
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

router = APIRouter(prefix="/watchlist/me", tags=["Watchlist (My)"])


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


class WatchlistQuickAdd(BaseModel):
    content_id: UUID


@router.get("/watchlist", response_model=List[WatchlistListItem])
def my_watchlist(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    profile_id: Optional[UUID] = Query(None, description="Filter by specific profile (must belong to user)"),
    content_id: Optional[UUID] = Query(None, description="Filter by content ID"),
    q_title: Optional[str] = Query(None, description="Search by content title (ilike)"),
    added_from: Optional[datetime] = Query(None),
    added_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[WatchlistListItem]:
    """
    Get the current user's watchlist items across all their profiles.
    """
    # Get all profiles belonging to the current user
    user_profiles = db.query(Profile).filter(Profile.user_id == me.id).all()
    if not user_profiles:
        return []
    
    profile_ids = [profile.id for profile in user_profiles]
    
    # Start with base query for user's profiles
    q = db.query(Watchlist).filter(Watchlist.profile_id.in_(profile_ids))
    
    # Apply filters
    if profile_id:
        # Ensure the requested profile belongs to the user
        if profile_id not in profile_ids:
            raise HTTPException(
                status_code=403, 
                detail="Profile does not belong to current user"
            )
        q = q.filter(Watchlist.profile_id == profile_id)
    
    if content_id:
        q = q.filter(Watchlist.content_id == content_id)
    
    if added_from:
        q = q.filter(Watchlist.added_at >= added_from)
    
    if added_to:
        q = q.filter(Watchlist.added_at <= added_to)
    
    if q_title:
        like = f"%{q_title.lower()}%"
        q = q.join(Content, Content.id == Watchlist.content_id).filter(
            func.lower(Content.title).ilike(like)
        )

    q = q.order_by(Watchlist.added_at.desc(), Watchlist.created_at.desc())
    return q.limit(limit).offset(offset).all()


@router.get("/watchlist/{watchlist_id}", response_model=WatchlistOut)
def get_my_watchlist_item(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Watchlist:
    """
    Get a specific watchlist item belonging to the current user.
    """
    item = db.get(Watchlist, watchlist_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    
    # Verify the item belongs to one of the user's profiles
    user_profile_ids = [p.id for p in db.query(Profile).filter(Profile.user_id == me.id).all()]
    if item.profile_id not in user_profile_ids:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    
    return item


@router.post("/watchlist", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def add_to_my_watchlist(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Watchlist:
    """
    Add content to the current user's watchlist.
    
    The profile_id in the payload must belong to the current user.
    """
    # Verify the profile belongs to the current user
    _ensure_profile_belongs_to_user(db, payload.profile_id, me.id)
    
    # Verify the content exists
    if not db.get(Content, payload.content_id):
        raise HTTPException(status_code=404, detail="Content not found")

    # Check for duplicates
    if _exists_watchlist_item(db, payload.profile_id, payload.content_id):
        raise HTTPException(status_code=409, detail="Item already exists in watchlist")

    entity = Watchlist(
        profile_id=payload.profile_id,
        content_id=payload.content_id,
        created_by=me.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/watchlist/{watchlist_id}", response_model=WatchlistOut)
def update_my_watchlist_item(
    watchlist_id: UUID,
    payload: WatchlistUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Watchlist:
    """
    Update a watchlist item belonging to the current user.
    """
    entity = db.get(Watchlist, watchlist_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    
    # Verify the item belongs to one of the user's profiles
    user_profile_ids = [p.id for p in db.query(Profile).filter(Profile.user_id == me.id).all()]
    if entity.profile_id not in user_profile_ids:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    new_profile_id = payload.profile_id or entity.profile_id
    new_content_id = payload.content_id or entity.content_id

    # If changing profile, verify it belongs to user
    if new_profile_id != entity.profile_id:
        _ensure_profile_belongs_to_user(db, new_profile_id, me.id)

    # Verify content exists if changing
    if new_content_id != entity.content_id:
        if not db.get(Content, new_content_id):
            raise HTTPException(status_code=404, detail="Content not found")

    # Check for duplicates if combination is changing
    if (new_profile_id != entity.profile_id) or (new_content_id != entity.content_id):
        if _exists_watchlist_item(db, new_profile_id, new_content_id):
            raise HTTPException(
                status_code=409, detail="Item already exists in watchlist"
            )
        entity.profile_id = new_profile_id
        entity.content_id = new_content_id

    entity.updated_by = me.id
    db.commit()
    db.refresh(entity)
    return entity


@router.delete("/watchlist/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_my_watchlist(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Response:
    """
    Remove a watchlist item from the current user's watchlist.
    """
    entity = db.get(Watchlist, watchlist_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    
    # Verify the item belongs to one of the user's profiles
    user_profile_ids = [p.id for p in db.query(Profile).filter(Profile.user_id == me.id).all()]
    if entity.profile_id not in user_profile_ids:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    db.delete(entity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/watchlist/by-content/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_by_content_from_my_watchlist(
    content_id: UUID,
    profile_id: Optional[UUID] = Query(None, description="Specific profile to remove from (optional)"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Response:
    """
    Remove watchlist items by content ID from the current user's profiles.
    
    If profile_id is provided, only removes from that specific profile.
    If profile_id is not provided, removes from all user's profiles.
    """
    # Get user's profiles
    user_profiles = db.query(Profile).filter(Profile.user_id == me.id).all()
    if not user_profiles:
        raise HTTPException(status_code=404, detail="No profiles found for user")
    
    profile_ids = [profile.id for profile in user_profiles]
    
    # Build query
    q = db.query(Watchlist).filter(
        Watchlist.content_id == content_id,
        Watchlist.profile_id.in_(profile_ids)
    )
    
    if profile_id:
        # Verify the profile belongs to the user
        if profile_id not in profile_ids:
            raise HTTPException(
                status_code=403, 
                detail="Profile does not belong to current user"
            )
        q = q.filter(Watchlist.profile_id == profile_id)
    
    entities = q.all()
    if not entities:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    
    for entity in entities:
        db.delete(entity)
    
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Profile-specific endpoints for backward compatibility
profile_router = APIRouter(
    prefix="/profiles/{profile_id}/watchlist", tags=["Watchlist (My Profile)"]
)


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
) -> Response:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist item not found")

    db.delete(entity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@profile_router.delete(
    "/by-content/{content_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_by_content_from_my_profile_watchlist(
    profile_id: UUID,
    content_id: UUID,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> Response:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist item not found")

    db.delete(entity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)