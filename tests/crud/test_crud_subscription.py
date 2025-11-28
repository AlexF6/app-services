# tests/crud/test_crud_subscription.py
from uuid import uuid4
from datetime import date, timedelta, datetime

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.auditmixin import SubscriptionStatus
from app.core.security import get_password_hash


def _build_user(db: Session) -> User:
    """
    Crea un usuario válido para usar como dueño de la suscripción
    y como actor de auditoría (created_by / updated_by).
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Sub User",
        email=f"sub_user_{uuid4()}@example.com",
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


def _build_plan(db: Session, actor: User, name: str = "Basic Plan") -> Plan:
    """
    Crea un plan válido, usando al user como actor de auditoría.
    """
    plan = Plan(
        id=uuid4(),
        name=name,
        price=9.99,
        max_profiles=4,
        max_devices=2,
        video_quality="HD",
    )
    plan.created_by = actor.id
    plan.updated_by = actor.id

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _build_subscription(
    db: Session,
    user: User,
    plan: Plan,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> Subscription:
    """
    Crea una suscripción válida para un user y plan dados.
    """
    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=status,
        start_date=date.today(),
    )
    sub.created_by = user.id
    sub.updated_by = user.id

    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def test_create_subscription_db(db: Session):
    owner = _build_user(db)
    plan = _build_plan(db, owner)

    sub = _build_subscription(db, owner, plan)

    assert sub.id is not None
    assert sub.user_id == owner.id
    assert sub.plan_id == plan.id
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.start_date is not None


def test_update_subscription_fields(db: Session):
    owner = _build_user(db)
    plan = _build_plan(db, owner)
    sub = _build_subscription(db, owner, plan)

    new_end_date = date.today() + timedelta(days=30)
    new_renews_at = date.today() + timedelta(days=60)
    canceled_at = datetime.utcnow()

    sub.status = SubscriptionStatus.CANCELED
    sub.end_date = new_end_date
    sub.renews_at = new_renews_at
    sub.canceled_at = canceled_at
    sub.updated_by = owner.id

    db.add(sub)
    db.commit()
    db.refresh(sub)

    assert sub.status == SubscriptionStatus.CANCELED
    assert sub.end_date == new_end_date
    assert sub.renews_at == new_renews_at
    assert sub.canceled_at is not None


def test_subscription_requires_existing_user_fk(db: Session):
    """
    No debería poder crearse una Subscription con user_id inexistente.
    """
    actor = _build_user(db)
    plan = _build_plan(db, actor)

    fake_user_id = uuid4()

    sub = Subscription(
        user_id=fake_user_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
    )
    sub.created_by = actor.id
    sub.updated_by = actor.id

    db.add(sub)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_subscription_requires_existing_plan_fk(db: Session):
    """
    No debería poder crearse una Subscription con plan_id inexistente.
    """
    owner = _build_user(db)
    fake_plan_id = uuid4()

    sub = Subscription(
        user_id=owner.id,
        plan_id=fake_plan_id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
    )
    sub.created_by = owner.id
    sub.updated_by = owner.id

    db.add(sub)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_delete_user_cascades_to_subscriptions(db: Session):
    """
    Verificamos que subscriptions.user_id (ondelete='CASCADE') elimine
    las suscripciones cuando se borra el usuario.
    Para que SQLite no bloquee por otros FKs (created_by/updated_by),
    hacemos que todos esos FKs apunten a otro usuario distinto.
    """
    audit_user = _build_user(db)

    owner = _build_user(db)

    plan = _build_plan(db, audit_user)

    sub = _build_subscription(db, owner, plan)
    sub_id = sub.id

    owner.created_by = audit_user.id
    owner.updated_by = audit_user.id

    sub.created_by = audit_user.id
    sub.updated_by = audit_user.id

    db.add_all([owner, sub])
    db.commit()

    db.delete(owner)
    db.commit()

    deleted = db.query(Subscription).filter(Subscription.id == sub_id).first()
    assert deleted is None


def test_delete_plan_restricted_when_subscription_exists(db: Session):
    """
    ondelete='RESTRICT' en plan_id -> no se debería poder borrar el plan
    si tiene suscripciones asociadas.
    """
    owner = _build_user(db)
    plan = _build_plan(db, owner)
    sub = _build_subscription(db, owner, plan)

    db.refresh(plan)
    db.refresh(sub)

    db.delete(plan)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()

    still_exists = db.query(Subscription).filter(Subscription.id == sub.id).first()
    assert still_exists is not None
