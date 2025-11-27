from uuid import uuid4
from datetime import date
from fastapi.testclient import TestClient

from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.auditmixin import SubscriptionStatus
from app.core.security import get_password_hash, create_access_token

def get_user_headers(client: TestClient, db, email_prefix="user_me"):
    email = f"{email_prefix}_{uuid4()}@test.com"
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Regular User",
        email=email,
        password=get_password_hash("user123"),
        active=True,
        is_admin=False,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}, user


def create_dummy_plan(db, owner: User, name="Pro Plan"):
    plan_id = uuid4()
    plan = Plan(
        id=plan_id,
        name=name,
        price=19.99,
        max_profiles=4,
        max_devices=2,
        video_quality="UHD",
        created_by=owner.id,
        updated_by=owner.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def test_me_create_subscription(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    plan = create_dummy_plan(db, user)

    user_id = user.id
    plan_id = plan.id

    payload = {
        "plan_id": str(plan_id),
        "start_date": str(date.today()),
    }

    response = client.post("/me/subscriptions", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert data["plan_id"] == str(plan_id)
    assert data["status"] == "ACTIVE"


def test_me_create_duplicate_active_fails(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    plan = create_dummy_plan(db, user)
    plan_id = plan.id

    client.post("/me/subscriptions", json={"plan_id": str(plan_id)}, headers=headers)

    response = client.post("/me/subscriptions", json={"plan_id": str(plan_id)}, headers=headers)

    assert response.status_code == 409
    assert "already have an active subscription" in response.json()["detail"]


def test_me_get_current_subscription(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    plan = create_dummy_plan(db, user)

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

    response = client.get("/me/subscriptions/current", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(sub_id)


def test_me_get_current_subscription_none(client: TestClient, db):
    headers, user = get_user_headers(client, db)

    response = client.get("/me/subscriptions/current", headers=headers)

    assert response.status_code == 404
    assert "No active subscription" in response.json()["detail"]


def test_me_list_subscriptions(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    plan = create_dummy_plan(db, user)

    s1 = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.CANCELED,
        start_date=date.today(),
        created_by=user.id,
        updated_by=user.id,
    )
    s2 = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add_all([s1, s2])
    db.commit()

    response = client.get("/me/subscriptions", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_me_switch_plan(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    plan1 = create_dummy_plan(db, user, "Basic")
    plan2 = create_dummy_plan(db, user, "Premium")

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
    target_plan_id = plan2.id

    payload = {
        "plan_id": str(target_plan_id),
    }

    response = client.post(
        f"/me/subscriptions/{sub_id}/switch-plan", json=payload, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["plan_id"] == str(target_plan_id)


def test_me_cancel_subscription(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    plan = create_dummy_plan(db, user)

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

    response = client.post(f"/me/subscriptions/{sub_id}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELED"


def test_me_cannot_access_others_subscription(client: TestClient, db):
    headers_a, user_a = get_user_headers(client, db, "victim_sub")
    plan = create_dummy_plan(db, user_a)

    sub = Subscription(
        user_id=user_a.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
        created_by=user_a.id,
        updated_by=user_a.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    sub_id = sub.id

    headers_b, user_b = get_user_headers(client, db, "attacker_sub")

    response = client.get(f"/me/subscriptions/{sub_id}", headers=headers_b)
    assert response.status_code == 404

    response_cancel = client.post(f"/me/subscriptions/{sub_id}/cancel", headers=headers_b)
    assert response_cancel.status_code == 404
