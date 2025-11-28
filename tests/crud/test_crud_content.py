# tests/crud/test_crud_content.py

from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.content import Content
from app.models.auditmixin import ContentType
from app.core.security import get_password_hash


def _build_actor_user(db: Session) -> User:
    """
    Usuario que vamos a usar como 'actor' para created_by / updated_by.
    Así cumplimos el FK hacia users.id.
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Content Admin",
        email=f"content_actor_{uuid4()}@example.com",
        password=get_password_hash("123456"),
        active=True,
        is_admin=True,
    )
    # audit
    user.created_by = user_id
    user.updated_by = user_id

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_content(actor: User, title: str | None = None) -> Content:
    """
    Crea un Content usando el actor como created_by / updated_by.
    """
    if title is None:
        title = f"Test Content {uuid4()}"

    content = Content(
        title=title,
        type=ContentType.MOVIE,
        description="Test description",
        release_year=2024,
        duration_seconds=3600,
        age_rating="PG",
        genres="Drama, Action",
        video_url="https://example.com/video.mp4",
        thumbnail="https://example.com/thumb.jpg",
    )

    content.created_by = actor.id
    content.updated_by = actor.id
    return content


def test_create_content_db(db: Session):
    actor = _build_actor_user(db)
    content = _build_content(actor)

    db.add(content)
    db.commit()
    db.refresh(content)

    assert content.id is not None
    assert content.title.startswith("Test Content")
    assert content.type == ContentType.MOVIE
    assert content.duration_seconds == 3600
    assert content.created_by == actor.id


def test_update_content_fields(db: Session):
    actor = _build_actor_user(db)
    content = _build_content(actor, title="Original Title")

    db.add(content)
    db.commit()
    db.refresh(content)

    content.title = "Updated Title"
    content.description = "Updated description"
    content.duration_seconds = 5400
    content.updated_by = actor.id

    db.add(content)
    db.commit()
    db.refresh(content)

    assert content.title == "Updated Title"
    assert content.description == "Updated description"
    assert content.duration_seconds == 5400
