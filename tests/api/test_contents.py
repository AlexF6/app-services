from fastapi.testclient import TestClient
from uuid import uuid4
from app.models.user import User
from app.core.security import get_password_hash, create_access_token

def get_admin_headers(client: TestClient, db):
    existing_admin = db.query(User).filter(User.email == "admin_content@test.com").first()
    
    if existing_admin:
        user_id = existing_admin.id
    else:
        user_id = uuid4()
        admin_user = User(
            id=user_id,
            name="Admin User",
            email="admin_content@test.com",
            password=get_password_hash("admin123"),
            active=True,
            is_admin=True,
            created_by=user_id
        )
        db.add(admin_user)
        db.commit()
    
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}

def test_create_content(client: TestClient, db):
    headers = get_admin_headers(client, db)
    
    payload = {
        "title": "Matrix Test",
        "type": "MOVIE",
        "description": "Sci-fi classic",
        "release_year": 1999,
        "duration_seconds": 7200,
        "age_rating": "R",
        "genres": "Action, Sci-Fi"
    }
    
    response = client.post("/contents", json=payload, headers=headers)
    
    if response.status_code == 422:
        print(response.json())

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Matrix Test"
    assert "id" in data

def test_list_contents_pagination(client: TestClient, db):
    headers = get_admin_headers(client, db)
    
    client.post("/contents", json={
        "title": "Dummy Movie",
        "type": "MOVIE",
        "release_year": 2020,
        "duration_seconds": 120
    }, headers=headers)
    
    response = client.get("/contents?limit=10&offset=0", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

def test_update_content(client: TestClient, db):
    headers = get_admin_headers(client, db)

    create_resp = client.post("/contents", json={
        "title": "To Update",
        "type": "VIDEOS",
        "release_year": 2000
    }, headers=headers)
    content_id = create_resp.json()["id"]

    update_payload = {
        "title": "Updated Title",
        "description": "New description"
    }
    response = client.put(f"/contents/{content_id}", json=update_payload, headers=headers)
    
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"

def test_delete_content(client: TestClient, db):
    headers = get_admin_headers(client, db)
    
    create_resp = client.post("/contents", json={
        "title": "To Delete",
        "type": "VIDEOS",
        "release_year": 2021
    }, headers=headers)
    content_id = create_resp.json()["id"]
    
    response = client.delete(f"/contents/{content_id}", headers=headers)
    assert response.status_code == 204
    
    get_resp = client.get(f"/contents/{content_id}", headers=headers)
    assert get_resp.status_code == 404