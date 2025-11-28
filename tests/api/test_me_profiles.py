from uuid import uuid4
from fastapi.testclient import TestClient
from app.models.user import User
from app.core.security import get_password_hash, create_access_token

def get_user_headers(client: TestClient, db, email_prefix="user"):
    email = f"{email_prefix}_{uuid4()}@test.com"
    user_id = uuid4()
    user = User(
        id=user_id,
        name="Regular User",
        email=email,
        password=get_password_hash("user123"),
        active=True,
        is_admin=False,
        created_by=user_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}, user

def test_me_create_profile(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    user_id = user.id
    
    payload = {
        "name": "My Profile",
        "maturity_rating": "R",
        "avatar": "http://img.com/1.png"
    }
    
    response = client.post("/me/profiles", json=payload, headers=headers)
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Profile"
    assert data["user_id"] == str(user_id)

def test_me_list_profiles(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    
    # Crear 2 perfiles
    client.post("/me/profiles", json={"name": "P1", "maturity_rating": "G"}, headers=headers)
    client.post("/me/profiles", json={"name": "P2", "maturity_rating": "PG"}, headers=headers)
    
    response = client.get("/me/profiles", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = [p["name"] for p in data]
    assert "P1" in names
    assert "P2" in names

def test_me_update_own_profile(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    
    create_resp = client.post("/me/profiles", json={"name": "Original", "maturity_rating": "G"}, headers=headers)
    profile_id = create_resp.json()["id"]
    
    response = client.put(f"/me/profiles/{profile_id}", json={"name": "Updated"}, headers=headers)
    
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"

def test_me_delete_own_profile(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    
    create_resp = client.post("/me/profiles", json={"name": "Delete Me", "maturity_rating": "G"}, headers=headers)
    profile_id = create_resp.json()["id"]
    
    response = client.delete(f"/me/profiles/{profile_id}", headers=headers)
    assert response.status_code == 204
    
    list_resp = client.get("/me/profiles", headers=headers)
    ids = [p["id"] for p in list_resp.json()]
    assert profile_id not in ids

def test_me_cannot_access_others_profile(client: TestClient, db):
    headers_a, user_a = get_user_headers(client, db, "victim")
    resp_a = client.post("/me/profiles", json={"name": "Victim Profile", "maturity_rating": "G"}, headers=headers_a)
    profile_id_a = resp_a.json()["id"]
    
    headers_b, user_b = get_user_headers(client, db, "attacker")
    
    response = client.delete(f"/me/profiles/{profile_id_a}", headers=headers_b)
    
    assert response.status_code == 403

def test_me_create_duplicate_name_fails(client: TestClient, db):
    headers, user = get_user_headers(client, db)
    
    client.post("/me/profiles", json={"name": "Unique", "maturity_rating": "G"}, headers=headers)
    
    response = client.post("/me/profiles", json={"name": "unique", "maturity_rating": "PG"}, headers=headers)
    
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]