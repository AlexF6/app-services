from uuid import uuid4
from datetime import date
from fastapi.testclient import TestClient

from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.auditmixin import SubscriptionStatus
from app.core.security import get_password_hash, create_access_token


def ensure_admin_user(db) -> User:
    """
    Crea (o reutiliza) un admin consistente para usar en headers y como actor (created_by/updated_by).
    """
    admin = db.query(User).filter(User.email == "admin_sub@test.com").first()
    if admin:
        return admin

    admin_id = uuid4()
    admin = User(
        id=admin_id,
        name="Admin User",
        email="admin_sub@test.com",
        password=get_password_hash("admin123"),
        active=True,
        is_admin=True,
        created_by=admin_id,
        updated_by=admin_id,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def get_admin_headers(client: TestClient, db):
    admin = ensure_admin_user(db)
    token = create_access_token(data={"sub": str(admin.id)})
    return {"Authorization": f"Bearer {token}"}


def create_dummy_user(db):
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Sub User",
        email=f"sub_user_{uuid4()}@test.com",
        password=get_password_hash("123456"),
        active=True,
        is_admin=False,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_dummy_plan(db, name="Basic Plan"):
    """
    El plan debe tener un created_by válido -> usamos el admin.
    """
    admin = ensure_admin_user(db)
    plan_id = uuid4()
    plan = Plan(
        id=plan_id,
        name=name,
        price=9.99,
        max_profiles=4,
        max_devices=2,
        video_quality="HD",
        created_by=admin.id,
        updated_by=admin.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def test_admin_create_subscription(client: TestClient, db):
    headers = get_admin_headers(client, db)
    user = create_dummy_user(db)
    plan = create_dummy_plan(db)

    user_id = user.id
    plan_id = plan.id

    payload = {
        "user_id": str(user_id),
        "plan_id": str(plan_id),
        "status": "ACTIVE",
        "start_date": str(date.today()),
    }

    response = client.post("/subscriptions", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert data["plan_id"] == str(plan_id)
    assert data["status"] == "ACTIVE"


def test_admin_create_subscription_conflict(client: TestClient, db):
    headers = get_admin_headers(client, db)
    user = create_dummy_user(db)
    plan = create_dummy_plan(db)

    user_id = user.id
    plan_id = plan.id

    sub = Subscription(
        user_id=user_id,
        plan_id=plan_id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(sub)
    db.commit()

    payload = {
        "user_id": str(user_id),
        "plan_id": str(plan_id),
        "status": "ACTIVE",
        "start_date": str(date.today()),
    }

    response = client.post("/subscriptions", json=payload, headers=headers)

    assert response.status_code == 409
    assert "already has an active subscription" in response.json()["detail"]


def test_admin_list_subscriptions(client: TestClient, db):
    headers = get_admin_headers(client, db)
    user = create_dummy_user(db)
    plan = create_dummy_plan(db)

    user_id = user.id
    plan_id = plan.id

    sub = Subscription(
        user_id=user_id,
        plan_id=plan_id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(sub)
    db.commit()

    response = client.get(f"/subscriptions?user_id={user_id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["user_id"] == str(user_id)


def test_admin_cancel_subscription(client: TestClient, db):
    headers = get_admin_headers(client, db)
    user = create_dummy_user(db)
    plan = create_dummy_plan(db)

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    sub_id = sub.id

    response = client.post(f"/subscriptions/{sub_id}/cancel", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CANCELED"
    assert data["canceled_at"] is not None


def test_admin_reactivate_subscription(client: TestClient, db):
    headers = get_admin_headers(client, db)
    user = create_dummy_user(db)
    plan = create_dummy_plan(db)

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.CANCELED,
        start_date=date.today(),
        canceled_at=date.today(),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    sub_id = sub.id

    response = client.post(f"/subscriptions/{sub_id}/reactivate", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ACTIVE"
    assert data["canceled_at"] is None


def test_admin_update_subscription_plan(client: TestClient, db):
    headers = get_admin_headers(client, db)
    user = create_dummy_user(db)
    plan1 = create_dummy_plan(db, "Plan 1")
    plan2 = create_dummy_plan(db, "Plan 2")

    sub = Subscription(
        user_id=user.id,
        plan_id=plan1.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    sub_id = sub.id
    new_plan_id = plan2.id

    payload = {"plan_id": str(new_plan_id)}

    response = client.put(f"/subscriptions/{sub_id}", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json()["plan_id"] == str(new_plan_id)
