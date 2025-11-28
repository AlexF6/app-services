from uuid import uuid4
from fastapi.testclient import TestClient
from app.models.user import User
from app.core.security import get_password_hash, create_access_token

def get_admin_headers(client: TestClient, db):
    existing_admin = db.query(User).filter(User.email == "admin_profiles@test.com").first()
    
    if existing_admin:
        user_id = existing_admin.id
    else:
        user_id = uuid4()
        admin_user = User(
            id=user_id,
            name="Admin User",
            email="admin_profiles@test.com",
            password=get_password_hash("admin123"),
            active=True,
            is_admin=True,
            created_by=user_id
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
    
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}

def create_dummy_user(db):
    """Crea un usuario estándar para asignarle perfiles"""
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Target User",
        email=f"target_{uuid4()}@test.com",
        password=get_password_hash("123456"),
        active=True,
        is_admin=False,
        created_by=user_id
    )
    db.add(user)
    db.commit()
    db.refresh(user) 
    return user


def test_admin_create_profile(client: TestClient, db):
    headers = get_admin_headers(client, db)
    target_user = create_dummy_user(db)
    target_user_id = target_user.id
    
    payload = {
        "user_id": str(target_user_id),
        "name": "Kids Profile",
        "maturity_rating": "PG",
        "avatar": "http://example.com/avatar.png"
    }
    
    response = client.post("/profiles", json=payload, headers=headers)
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Kids Profile"
    assert data["user_id"] == str(target_user_id)
    assert "id" in data

def test_admin_create_duplicate_profile_name_fails(client: TestClient, db):
    headers = get_admin_headers(client, db)
    target_user = create_dummy_user(db)
    target_user_id = target_user.id
    
    payload = {
        "user_id": str(target_user_id),
        "name": "Main Profile",
        "maturity_rating": "R"
    }

    client.post("/profiles", json=payload, headers=headers)

    response = client.post("/profiles", json=payload, headers=headers)
    
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

def test_admin_list_profiles(client: TestClient, db):
    headers = get_admin_headers(client, db)
    target_user = create_dummy_user(db)
    target_user_id = target_user.id

    client.post("/profiles", json={
        "user_id": str(target_user_id),
        "name": "Search Me",
        "maturity_rating": "G"
    }, headers=headers)

    response = client.get(f"/profiles?user_id={target_user_id}", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "Search Me"

def test_admin_update_profile(client: TestClient, db):
    headers = get_admin_headers(client, db)
    target_user = create_dummy_user(db)
    target_user_id = target_user.id
    
    create_resp = client.post("/profiles", json={
        "user_id": str(target_user_id),
        "name": "Old Name",
        "maturity_rating": "PG"
    }, headers=headers)
    profile_id = create_resp.json()["id"]
    
    update_payload = {
        "name": "New Name",
        "maturity_rating": "MA"
    }
    
    response = client.put(f"/profiles/{profile_id}", json=update_payload, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["maturity_rating"] == "MA"

def test_admin_delete_profile(client: TestClient, db):
    headers = get_admin_headers(client, db)
    target_user = create_dummy_user(db)
    target_user_id = target_user.id
    
    create_resp = client.post("/profiles", json={
        "user_id": str(target_user_id),
        "name": "To Delete",
        "maturity_rating": "G"
    }, headers=headers)
    profile_id = create_resp.json()["id"]
    
    response = client.delete(f"/profiles/{profile_id}", headers=headers)
    assert response.status_code == 204
    
    # Verificar que ya no existe
    get_resp = client.get(f"/profiles/{profile_id}", headers=headers)
    assert get_resp.status_code == 404