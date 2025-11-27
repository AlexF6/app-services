# tests/crud/test_auditmixin_and_enums.py

from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.content import Content
from app.models.auditmixin import (
    AuditMixin,
    ContentType,
    SubscriptionStatus,
    PaymentStatus,
)
from app.core.security import get_password_hash


def _build_user(db: Session) -> User:
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Audit User",
        email=f"audit_user_{uuid4()}@example.com",
        password=get_password_hash("audit123"),
        active=True,
        is_admin=False,
    )
    user.created_by = user_id
    user.updated_by = user_id

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def test_content_type_enum_values():
    assert ContentType.MOVIE.value == "MOVIE"
    assert ContentType.SERIES.value == "SERIES"
    assert ContentType.VIDEOS.value == "VIDEOS"


def test_subscription_status_enum_values():
    assert SubscriptionStatus.ACTIVE.value == "ACTIVE"
    assert SubscriptionStatus.CANCELED.value == "CANCELED"
    assert SubscriptionStatus.PAST_DUE.value == "PAST_DUE"


def test_payment_status_enum_values():
    assert PaymentStatus.PENDING.value == "PENDING"
    assert PaymentStatus.PAID.value == "PAID"
    assert PaymentStatus.FAILED.value == "FAILED"
    assert PaymentStatus.REFUNDED.value == "REFUNDED"

def _build_content(db: Session, actor: User) -> Content:
    content = Content(
        title="Audit Test Content",
        type=ContentType.MOVIE,
        description="Testing audit mixin",
        release_year=2024,
        duration_seconds=1200,
        age_rating="PG-13",
    )
    content.created_by = actor.id
    content.updated_by = actor.id

    db.add(content)
    db.commit()
    db.refresh(content)
    return content


def test_audit_fields_on_insert(db: Session):
    """
    Al crear un registro que hereda de AuditMixin:
    - created_at se setea automáticamente
    - updated_at inicialmente es NULL
    - created_by / updated_by respetan la FK a users.id
    """
    actor = _build_user(db)
    content = _build_content(db, actor)

    assert content.created_by == actor.id
    assert content.updated_by == actor.id
    assert content.created_at is not None
    assert content.updated_at is None


def test_audit_fields_on_update(db: Session):
    """
    Al actualizar el registro:
    - updated_at deja de ser NULL
    - created_at se mantiene
    """
    actor = _build_user(db)
    content = _build_content(db, actor)

    original_created_at = content.created_at

    content.title = "Updated Title"
    content.updated_by = actor.id

    db.add(content)
    db.commit()
    db.refresh(content)

    assert content.created_at == original_created_at
    assert content.updated_at is not None
    assert content.updated_at >= content.created_at
