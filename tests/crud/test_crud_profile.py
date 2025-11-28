# tests/crud/test_crud_profile.py

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.profile import Profile
from app.core.security import get_password_hash


def _build_user(db: Session) -> User:
    """
    Crea un usuario válido para usar como dueño de perfiles
    y como actor de auditoría (created_by / updated_by).
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Profile Owner",
        email=f"profile_owner_{uuid4()}@example.com",
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


def _build_profile(owner: User, name: str = "Main Profile", maturity: str = "G") -> Profile:
    """
    Construye un Profile en memoria usando el user como dueño
    y como actor de auditoría.
    """
    profile = Profile(
        user_id=owner.id,
        name=name,
        maturity_rating=maturity,
    )
    profile.created_by = owner.id
    profile.updated_by = owner.id
    return profile


def test_create_profile_db(db: Session):
    owner = _build_user(db)
    profile = _build_profile(owner)

    db.add(profile)
    db.commit()
    db.refresh(profile)

    assert profile.id is not None
    assert profile.user_id == owner.id
    assert profile.name == "Main Profile"
    assert profile.maturity_rating == "G"


def test_update_profile_fields(db: Session):
    owner = _build_user(db)
    profile = _build_profile(owner, name="Kid", maturity="G")

    db.add(profile)
    db.commit()
    db.refresh(profile)

    profile.name = "Teen Profile"
    profile.maturity_rating = "PG-13"
    profile.avatar = "https://example.com/avatar.png"
    profile.updated_by = owner.id

    db.add(profile)
    db.commit()
    db.refresh(profile)

    assert profile.name == "Teen Profile"
    assert profile.maturity_rating == "PG-13"
    assert profile.avatar == "https://example.com/avatar.png"


def test_profile_requires_existing_user_fk(db: Session):
    """
    No debería poder crearse un Profile con user_id que no exista.
    """
    actor = _build_user(db)

    fake_user_id = uuid4()
    profile = Profile(
        user_id=fake_user_id,
        name="Orphan Profile",
        maturity_rating="G",
    )
    profile.created_by = actor.id
    profile.updated_by = actor.id

    db.add(profile)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_delete_user_cascades_to_profiles(db: Session):
    """
    Al borrar un User, sus Profiles deben borrarse en cascada
    (ondelete='CASCADE' en Profile.user_id).
    """
    owner = _build_user(db)
    profile = _build_profile(owner)
    db.add(profile)
    db.commit()
    db.refresh(profile)

    profile_id = profile.id

    db.delete(owner)
    db.commit()

    deleted_profile = db.query(Profile).filter(Profile.id == profile_id).first()
    assert deleted_profile is None
