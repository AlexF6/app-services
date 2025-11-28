# tests/crud/test_crud_plan.py

from uuid import uuid4
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.plan import Plan
from app.core.security import get_password_hash


def _build_actor(db: Session) -> User:
    """
    Usuario actor para los campos de auditoría (created_by / updated_by).
    NO se borra en los tests.
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Audit Actor",
        email=f"actor_plan_{uuid4()}@example.com",
        password=get_password_hash("actor123"),
        active=True,
        is_admin=True,
    )
    # self-reference para cumplir FK de AuditMixin
    user.created_by = user_id
    user.updated_by = user_id

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_plan(
    db: Session,
    actor: User,
    name: str = "Basic Plan",
    price: Decimal = Decimal("9.99"),
    max_profiles: int = 4,
    max_devices: int = 2,
    video_quality: str = "HD",
) -> Plan:
    """
    Crea un Plan válido con auditoría apuntando al actor.
    """
    plan = Plan(
        id=uuid4(),
        name=name,
        price=price,
        max_profiles=max_profiles,
        max_devices=max_devices,
        video_quality=video_quality,
    )
    plan.created_by = actor.id
    plan.updated_by = actor.id

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def test_create_plan_db(db: Session):
    actor = _build_actor(db)

    plan = _build_plan(db, actor)

    assert plan.id is not None
    assert plan.name == "Basic Plan"
    assert plan.price == Decimal("9.99")
    assert plan.max_profiles == 4
    assert plan.max_devices == 2
    assert plan.video_quality == "HD"
    assert plan.created_by == actor.id
    assert plan.updated_by == actor.id


def test_update_plan_fields(db: Session):
    actor = _build_actor(db)
    plan = _build_plan(db, actor)

    new_name = "Premium Plan"
    new_price = Decimal("19.99")
    new_max_profiles = 6
    new_max_devices = 4
    new_quality = "UHD"

    plan.name = new_name
    plan.price = new_price
    plan.max_profiles = new_max_profiles
    plan.max_devices = new_max_devices
    plan.video_quality = new_quality
    plan.updated_by = actor.id

    db.add(plan)
    db.commit()
    db.refresh(plan)

    assert plan.name == new_name
    assert plan.price == new_price
    assert plan.max_profiles == new_max_profiles
    assert plan.max_devices == new_max_devices
    assert plan.video_quality == new_quality


def test_plan_name_unique_constraint(db: Session):
    """
    name es unique -> no se pueden crear dos planes con el mismo nombre.
    """
    actor = _build_actor(db)

    _ = _build_plan(db, actor, name="Unique Plan")

    duplicate = Plan(
        id=uuid4(),
        name="Unique Plan",
        price=Decimal("5.00"),
        max_profiles=1,
        max_devices=1,
        video_quality="SD",
    )
    duplicate.created_by = actor.id
    duplicate.updated_by = actor.id

    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_delete_plan_without_subscriptions(db: Session):
    """
    Se debe poder borrar un plan que no tenga suscripciones asociadas.
    (No tocamos Subscription aquí para evitar conflictos con ondelete='RESTRICT')
    """
    actor = _build_actor(db)
    plan = _build_plan(db, actor, name="To Delete Plan")

    plan_id = plan.id

    db.delete(plan)
    db.commit()

    deleted = db.query(Plan).filter(Plan.id == plan_id).first()
    assert deleted is None
