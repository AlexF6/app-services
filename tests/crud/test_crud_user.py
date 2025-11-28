# crud/test_crud_user.py
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import uuid4

from app.models.user import User
from app.models.profile import Profile
from app.core.security import get_password_hash


def _build_user(email: str, name: str, password: str) -> User:
    """
    Helper para crear un User con created_by / updated_by válidos
    (autorreferencia para satisfacer la FK en tests con SQLite).
    """
    user = User(
        email=email,
        name=name,
        password=get_password_hash(password),
        active=True,
    )

    if user.id is None:
        user.id = uuid4()

    user.created_by = user.id
    user.updated_by = user.id
    return user


def _build_profile_for_user(user: User, name: str, maturity: str) -> Profile:
    """
    Helper para crear un Profile con FKs válidas.
    """
    profile = Profile(
        user_id=user.id,
        name=name,
        maturity_rating=maturity,
    )

    profile.created_by = user.id
    profile.updated_by = user.id
    return profile


def test_create_user_db(db: Session):
    email = f"crud_{uuid4()}@example.com"
    password = "password123"

    user_in = _build_user(
        email=email,
        name="Test CRUD User",
        password=password,
    )

    db.add(user_in)
    db.commit()
    db.refresh(user_in)

    assert user_in.id is not None
    assert user_in.email == email
    assert user_in.is_admin is False


def test_create_user_duplicate_email_error(db: Session):
    email = f"dup_{uuid4()}@example.com"
    password = "pass"

    user1 = _build_user(
        email=email,
        name="User One",
        password=password,
    )
    db.add(user1)
    db.commit()

    user2 = _build_user(
        email=email,
        name="User Two",
        password=password,
    )
    db.add(user2)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_delete_user_cascades_to_profile(db: Session):
    user = _build_user(
        email=f"cascade_{uuid4()}@example.com",
        name="Parent User",
        password="123",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = _build_profile_for_user(
        user=user,
        name="Kid Profile",
        maturity="G",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    assert db.query(Profile).filter(Profile.user_id == user.id).count() == 1

    profile_id = profile.id

    db.delete(user)
    db.commit()

    deleted_profile = db.query(Profile).filter(Profile.id == profile_id).first()
    assert deleted_profile is None



def test_update_user_fields(db: Session):
    user = _build_user(
        email=f"update_{uuid4()}@example.com",
        name="Old Name",
        password="123",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user.name = "New Name"
    user.active = False
    user.updated_by = user.id

    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.name == "New Name"
    assert user.active is False
