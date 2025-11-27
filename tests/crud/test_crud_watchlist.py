# tests/crud/test_crud_watchlist.py

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.profile import Profile
from app.models.content import Content
from app.models.watchlist import Watchlist
from app.core.security import get_password_hash


def _build_actor(db: Session) -> User:
    """
    Usuario que usaremos como actor de auditoría (created_by/updated_by)
    y dueño de perfiles.
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Watchlist Actor",
        email=f"actor_watchlist_{uuid4()}@example.com",
        password=get_password_hash("watch123"),
        active=True,
        is_admin=True,
    )

    user.created_by = user_id
    user.updated_by = user_id

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_profile(db: Session, actor: User) -> Profile:
    """
    Profile asociado al actor.
    """
    profile = Profile(
        user_id=actor.id,
        name="Main Profile",
        avatar=None,
        maturity_rating="G",
    )
    profile.created_by = actor.id
    profile.updated_by = actor.id

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _build_content(db: Session, actor: User) -> Content:
    """
    Contenido genérico para usar en la watchlist.
    """
    content = Content(
        title="Sample Content",
        type="MOVIE",  # si tu Enum es str-based, esto funciona en SQLite
        description="Just a test content",
        release_year=2024,
        duration_seconds=3600,
        age_rating="PG",
    )
    content.created_by = actor.id
    content.updated_by = actor.id

    db.add(content)
    db.commit()
    db.refresh(content)
    return content


def _build_watchlist_item(
    db: Session, actor: User, profile: Profile, content: Content
) -> Watchlist:
    """
    Ítem válido de watchlist.
    """
    wl = Watchlist(
        profile_id=profile.id,
        content_id=content.id,
    )
    wl.created_by = actor.id
    wl.updated_by = actor.id

    db.add(wl)
    db.commit()
    db.refresh(wl)
    return wl


def test_create_watchlist_item_db(db: Session):
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)

    wl = _build_watchlist_item(db, actor, profile, content)

    assert wl.id is not None
    assert wl.profile_id == profile.id
    assert wl.content_id == content.id
    assert wl.created_by == actor.id
    assert wl.updated_by == actor.id
    # added_at viene del server_default
    assert wl.added_at is not None


def test_unique_profile_content_constraint(db: Session):
    """
    UniqueConstraint('profile_id', 'content_id') -> no se puede repetir el par.
    """
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)

    _ = _build_watchlist_item(db, actor, profile, content)

    wl_dup = Watchlist(
        profile_id=profile.id,
        content_id=content.id,
    )
    wl_dup.created_by = actor.id
    wl_dup.updated_by = actor.id

    db.add(wl_dup)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_watchlist_requires_existing_profile_fk(db: Session):
    """
    No se debe poder crear Watchlist con profile_id inexistente.
    """
    actor = _build_actor(db)
    content = _build_content(db, actor)

    fake_profile_id = uuid4()

    wl = Watchlist(
        profile_id=fake_profile_id,
        content_id=content.id,
    )
    wl.created_by = actor.id
    wl.updated_by = actor.id

    db.add(wl)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_watchlist_requires_existing_content_fk(db: Session):
    """
    No se debe poder crear Watchlist con content_id inexistente.
    """
    actor = _build_actor(db)
    profile = _build_profile(db, actor)

    fake_content_id = uuid4()

    wl = Watchlist(
        profile_id=profile.id,
        content_id=fake_content_id,
    )
    wl.created_by = actor.id
    wl.updated_by = actor.id

    db.add(wl)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_delete_profile_cascades_to_watchlist(db: Session):
    """
    ondelete='CASCADE' en profile_id -> al borrar el profile se borra la watchlist.
    """
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)

    wl = _build_watchlist_item(db, actor, profile, content)
    wl_id = wl.id

    db.delete(profile)
    db.commit()

    deleted = db.query(Watchlist).filter(Watchlist.id == wl_id).first()
    assert deleted is None


def test_delete_content_cascades_to_watchlist(db: Session):
    """
    ondelete='CASCADE' en content_id -> al borrar el content se borra la watchlist.
    """
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)

    wl = _build_watchlist_item(db, actor, profile, content)
    wl_id = wl.id

    db.delete(content)
    db.commit()

    deleted = db.query(Watchlist).filter(Watchlist.id == wl_id).first()
    assert deleted is None
