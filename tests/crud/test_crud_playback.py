# tests/crud/test_crud_playback.py

from uuid import uuid4
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.profile import Profile
from app.models.content import Content
from app.models.episode import Episode
from app.models.playback import Playback
from app.core.security import get_password_hash


def _build_actor(db: Session) -> User:
    """
    Usuario que usaremos como owner y actor de auditoría (created_by/updated_by).
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Playback Actor",
        email=f"actor_playback_{uuid4()}@example.com",
        password=get_password_hash("playback123"),
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
    Contenido genérico para usar en playbacks/episodes.
    """
    content = Content(
        title="Sample Movie",
        type="MOVIE",
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


def _build_episode(db: Session, actor: User, content: Content) -> Episode:
    """
    Episodio asociado al contenido (para simular series).
    """
    ep = Episode(
        content_id=content.id,
        season_number=1,
        episode_number=1,
        title="Pilot",
        duration_seconds=1800,
    )
    ep.created_by = actor.id
    ep.updated_by = actor.id

    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def _build_playback(
    db: Session,
    actor: User,
    profile: Profile,
    content: Content,
    episode: Episode | None = None,
) -> Playback:
    """
    Playback válido enlazando profile + content (+ opcionalmente episode).
    """
    pb = Playback(
        profile_id=profile.id,
        content_id=content.id,
        episode_id=episode.id if episode else None,
        progress_seconds=0,
        completed=False,
        device="Linux / Firefox",
        duration_seconds=content.duration_seconds,
    )
    pb.created_by = actor.id
    pb.updated_by = actor.id

    db.add(pb)
    db.commit()
    db.refresh(pb)
    return pb


def test_create_playback_db(db: Session):
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)
    episode = _build_episode(db, actor, content)

    pb = _build_playback(db, actor, profile, content, episode)

    assert pb.id is not None
    assert pb.profile_id == profile.id
    assert pb.content_id == content.id
    assert pb.episode_id == episode.id
    assert pb.progress_seconds == 0
    assert pb.completed is False
    assert pb.device == "Linux / Firefox"
    assert pb.created_by == actor.id
    assert pb.updated_by == actor.id


def test_update_playback_fields(db: Session):
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)

    pb = _build_playback(db, actor, profile, content)

    new_progress = 1200
    finished_at = datetime.now(timezone.utc)
    pb.progress_seconds = new_progress
    pb.completed = True
    pb.ended_at = finished_at
    pb.last_seen_at = finished_at
    pb.device = "Android TV"
    pb.updated_by = actor.id

    db.add(pb)
    db.commit()
    db.refresh(pb)

    assert pb.progress_seconds == new_progress
    assert pb.completed is True
    assert pb.ended_at is not None
    assert pb.last_seen_at is not None
    assert pb.device == "Android TV"


def test_playback_requires_existing_profile_fk(db: Session):
    """
    No se debe poder crear Playback con profile_id inexistente.
    """
    actor = _build_actor(db)
    content = _build_content(db, actor)

    fake_profile_id = uuid4()

    pb = Playback(
        profile_id=fake_profile_id,
        content_id=content.id,
    )
    pb.created_by = actor.id
    pb.updated_by = actor.id

    db.add(pb)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_playback_requires_existing_content_fk(db: Session):
    """
    No se debe poder crear Playback con content_id inexistente.
    """
    actor = _build_actor(db)
    profile = _build_profile(db, actor)

    fake_content_id = uuid4()

    pb = Playback(
        profile_id=profile.id,
        content_id=fake_content_id,
    )
    pb.created_by = actor.id
    pb.updated_by = actor.id

    db.add(pb)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_delete_profile_cascades_to_playbacks(db: Session):
    """
    ondelete='CASCADE' en profile_id -> al borrar el profile se borran los playbacks.
    """
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)

    pb = _build_playback(db, actor, profile, content)
    pb_id = pb.id

    db.delete(profile)
    db.commit()

    deleted = db.query(Playback).filter(Playback.id == pb_id).first()
    assert deleted is None


def test_delete_content_cascades_to_playbacks(db: Session):
    """
    ondelete='CASCADE' en content_id -> al borrar el content se borran los playbacks.
    (Aquí no usamos episode para simplificar la cascada).
    """
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)

    pb = _build_playback(db, actor, profile, content)
    pb_id = pb.id

    db.delete(content)
    db.commit()

    deleted = db.query(Playback).filter(Playback.id == pb_id).first()
    assert deleted is None


def test_progress_seconds_must_be_non_negative(db: Session):
    """
    CheckConstraint ck_playbacks_progress_nonneg -> progress_seconds >= 0
    """
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)

    pb = Playback(
        profile_id=profile.id,
        content_id=content.id,
        progress_seconds=-10,  # inválido
        completed=False,
    )
    pb.created_by = actor.id
    pb.updated_by = actor.id

    db.add(pb)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_duration_seconds_must_be_non_negative(db: Session):
    """
    CheckConstraint ck_playbacks_duration_nonneg:
    (duration_seconds IS NULL) OR (duration_seconds >= 0)
    """
    actor = _build_actor(db)
    profile = _build_profile(db, actor)
    content = _build_content(db, actor)

    pb = Playback(
        profile_id=profile.id,
        content_id=content.id,
        duration_seconds=-50,
    )
    pb.created_by = actor.id
    pb.updated_by = actor.id

    db.add(pb)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()
