# tests/crud/test_crud_episode.py

from uuid import uuid4
from datetime import date

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.content import Content
from app.models.episode import Episode
from app.models.auditmixin import ContentType
from app.core.security import get_password_hash


def _build_actor(db: Session) -> User:
    """
    Usuario que usaremos como actor de auditoría (created_by / updated_by).
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Actor User",
        email=f"actor_{uuid4()}@example.com",
        password=get_password_hash("123456"),
        active=True,
        is_admin=False,
    )

    user.created_by = user_id
    user.updated_by = user_id

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_content(db: Session, actor: User) -> Content:
    """
    Crea un Content válido, asociado al actor como created_by / updated_by.
    """
    content = Content(
        title="Test Show",
        type=ContentType.SERIES,
        description="A test series for episodes CRUD.",
        release_year=2024,
        duration_seconds=None,
        age_rating="PG",
    )
    content.created_by = actor.id
    content.updated_by = actor.id

    db.add(content)
    db.commit()
    db.refresh(content)
    return content


def _build_episode(
    db: Session,
    content: Content,
    actor: User,
    season_number: int = 1,
    episode_number: int = 1,
    title: str = "Pilot",
) -> Episode:
    """
    Crea un Episode válido para un contenido dado.
    """
    ep = Episode(
        content_id=content.id,
        season_number=season_number,
        episode_number=episode_number,
        title=title,
        duration_seconds=1800,
        release_date=date.today(),
        video_url="https://example.com/episode1.m3u8",
    )
    ep.created_by = actor.id
    ep.updated_by = actor.id

    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def test_create_episode_db(db: Session):
    actor = _build_actor(db)
    content = _build_content(db, actor)

    ep = _build_episode(db, content, actor)

    assert ep.id is not None
    assert ep.content_id == content.id
    assert ep.season_number == 1
    assert ep.episode_number == 1
    assert ep.title == "Pilot"
    assert ep.created_by == actor.id
    assert ep.updated_by == actor.id


def test_update_episode_fields(db: Session):
    actor = _build_actor(db)
    content = _build_content(db, actor)
    ep = _build_episode(db, content, actor)

    new_title = "Pilot – Extended Cut"
    new_duration = 2000
    new_season = 2
    new_episode_number = 3
    new_release_date = date(2025, 1, 1)

    ep.title = new_title
    ep.duration_seconds = new_duration
    ep.season_number = new_season
    ep.episode_number = new_episode_number
    ep.release_date = new_release_date
    ep.updated_by = actor.id

    db.add(ep)
    db.commit()
    db.refresh(ep)

    assert ep.title == new_title
    assert ep.duration_seconds == new_duration
    assert ep.season_number == new_season
    assert ep.episode_number == new_episode_number
    assert ep.release_date == new_release_date


def test_episode_requires_existing_content_fk(db: Session):
    """
    No debería poder crearse un Episode con content_id inexistente.
    """
    actor = _build_actor(db)
    fake_content_id = uuid4()

    ep = Episode(
        content_id=fake_content_id,
        season_number=1,
        episode_number=1,
        title="Orphan Episode",
        duration_seconds=1000,
        release_date=date.today(),
        video_url="https://example.com/orphan.m3u8",
    )
    ep.created_by = actor.id
    ep.updated_by = actor.id

    db.add(ep)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_delete_content_cascades_to_episodes(db: Session):
    """
    Verificamos que episodes.content_id (ondelete='CASCADE') elimine
    los episodios cuando se borra el contenido.
    """
    actor = _build_actor(db)
    content = _build_content(db, actor)
    ep = _build_episode(db, content, actor)

    ep_id = ep.id

    db.delete(content)
    db.commit()

    deleted = db.query(Episode).filter(Episode.id == ep_id).first()
    assert deleted is None


def test_multiple_episodes_same_content(db: Session):
    """
    Múltiples episodios para el mismo contenido se persisten correctamente.
    """
    actor = _build_actor(db)
    content = _build_content(db, actor)

    ep1 = _build_episode(db, content, actor, season_number=1, episode_number=1, title="Ep 1")
    ep2 = _build_episode(db, content, actor, season_number=1, episode_number=2, title="Ep 2")

    episodes = (
        db.query(Episode)
        .filter(Episode.content_id == content.id)
        .order_by(Episode.episode_number)
        .all()
    )

    assert len(episodes) == 2
    assert episodes[0].title == "Ep 1"
    assert episodes[1].title == "Ep 2"
