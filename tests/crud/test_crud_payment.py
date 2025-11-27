# tests/crud/test_crud_payment.py

from uuid import uuid4
from decimal import Decimal
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.auditmixin import SubscriptionStatus, PaymentStatus
from app.core.security import get_password_hash


def _build_actor(db: Session) -> User:
    """
    Usuario actor que usaremos para created_by / updated_by.
    No lo borramos en los tests de cascada.
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Audit Actor",
        email=f"actor_{uuid4()}@example.com",
        password=get_password_hash("actor123"),
        active=True,
        is_admin=True,
    )
    user.created_by = user_id
    user.updated_by = user_id

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_payer(db: Session, actor: User) -> User:
    """
    Usuario que representa al cliente que tiene suscripción y pagos.
    Sus campos de auditoría apuntan al actor.
    """
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Payer User",
        email=f"payer_{uuid4()}@example.com",
        password=get_password_hash("payer123"),
        active=True,
        is_admin=False,
    )
    user.created_by = actor.id
    user.updated_by = actor.id

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_plan(db: Session, actor: User, name: str = "Pro Plan") -> Plan:
    """
    Plan de suscripción, con auditoría apuntando al actor.
    """
    plan = Plan(
        id=uuid4(),
        name=name,
        price=Decimal("9.99"),
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
    payer: User,
    plan: Plan,
    actor: User,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> Subscription:
    """
    Suscripción del payer a un plan, con auditoría apuntando al actor.
    """
    sub = Subscription(
        user_id=payer.id,
        plan_id=plan.id,
        status=status,
        start_date=date.today(),
    )
    sub.created_by = actor.id
    sub.updated_by = actor.id

    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _build_payment(
    db: Session,
    payer: User,
    sub: Subscription,
    actor: User,
    status: PaymentStatus = PaymentStatus.PENDING,
    amount: Decimal = Decimal("9.99"),
) -> Payment:
    """
    Pago asociado a un usuario y a una suscripción.
    """
    pay = Payment(
        user_id=payer.id,
        subscription_id=sub.id,
        amount=amount,
        currency="USD",
        status=status,
        provider="STRIPE",
        external_id=f"pay_{uuid4()}",
    )
    pay.created_by = actor.id
    pay.updated_by = actor.id

    db.add(pay)
    db.commit()
    db.refresh(pay)
    return pay


def test_create_payment_db(db: Session):
    actor = _build_actor(db)
    payer = _build_payer(db, actor)
    plan = _build_plan(db, actor)
    sub = _build_subscription(db, payer, plan, actor)

    pay = _build_payment(db, payer, sub, actor)

    assert pay.id is not None
    assert pay.user_id == payer.id
    assert pay.subscription_id == sub.id
    assert pay.amount == Decimal("9.99")
    assert pay.currency == "USD"
    assert pay.status == PaymentStatus.PENDING
    assert pay.created_by == actor.id
    assert pay.updated_by == actor.id


def test_update_payment_fields(db: Session):
    actor = _build_actor(db)
    payer = _build_payer(db, actor)
    plan = _build_plan(db, actor)
    sub = _build_subscription(db, payer, plan, actor)
    pay = _build_payment(db, payer, sub, actor)

    new_amount = Decimal("14.99")
    new_status = PaymentStatus.PAID
    new_paid_at = datetime.now(timezone.utc)
    new_provider = "PAYPAL"
    new_external_id = f"paypal_{uuid4()}"

    pay.amount = new_amount
    pay.status = new_status
    pay.paid_at = new_paid_at
    pay.provider = new_provider
    pay.external_id = new_external_id
    pay.updated_by = actor.id

    db.add(pay)
    db.commit()
    db.refresh(pay)

    assert pay.amount == new_amount
    assert pay.status == new_status
    assert pay.paid_at is not None
    assert pay.provider == new_provider
    assert pay.external_id == new_external_id


def test_payment_requires_existing_user_fk(db: Session):
    """
    No debería poder crearse un Payment con un user_id inexistente.
    """
    actor = _build_actor(db)
    payer = _build_payer(db, actor)
    plan = _build_plan(db, actor)
    sub = _build_subscription(db, payer, plan, actor)

    fake_user_id = uuid4()

    pay = Payment(
        user_id=fake_user_id,
        subscription_id=sub.id,
        amount=Decimal("9.99"),
        currency="USD",
        status=PaymentStatus.PENDING,
        provider="STRIPE",
        external_id="fake_user_pay",
    )
    pay.created_by = actor.id
    pay.updated_by = actor.id

    db.add(pay)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_payment_requires_existing_subscription_fk(db: Session):
    """
    No debería poder crearse un Payment con subscription_id inexistente.
    """
    actor = _build_actor(db)
    payer = _build_payer(db, actor)

    fake_sub_id = uuid4()

    pay = Payment(
        user_id=payer.id,
        subscription_id=fake_sub_id,
        amount=Decimal("9.99"),
        currency="USD",
        status=PaymentStatus.PENDING,
        provider="STRIPE",
        external_id="fake_sub_pay",
    )
    pay.created_by = actor.id
    pay.updated_by = actor.id

    db.add(pay)
    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_delete_user_cascades_to_payments(db: Session):
    """
    ondelete='CASCADE' en payments.user_id y en subscriptions.user_id:
    al borrar el payer se deben borrar sus pagos (y sus suscripciones).
    """
    actor = _build_actor(db)
    payer = _build_payer(db, actor)
    plan = _build_plan(db, actor)
    sub = _build_subscription(db, payer, plan, actor)
    pay = _build_payment(db, payer, sub, actor)

    pay_id = pay.id

    db.delete(payer)
    db.commit()

    deleted = db.query(Payment).filter(Payment.id == pay_id).first()
    assert deleted is None


def test_delete_subscription_cascades_to_payments(db: Session):
    """
    ondelete='CASCADE' en payments.subscription_id:
    al borrar la suscripción, se deben borrar los pagos asociados.
    """
    actor = _build_actor(db)
    payer = _build_payer(db, actor)
    plan = _build_plan(db, actor)
    sub = _build_subscription(db, payer, plan, actor)
    pay = _build_payment(db, payer, sub, actor)

    pay_id = pay.id

    db.delete(sub)
    db.commit()

    deleted = db.query(Payment).filter(Payment.id == pay_id).first()
    assert deleted is None
