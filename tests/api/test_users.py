from fastapi.testclient import TestClient
from uuid import uuid4
from app.models.user import User
from app.core.security import get_password_hash, create_access_token

def get_admin_headers(client: TestClient, db):
    admin_id = uuid4()
    admin_user = User(
        id=admin_id,
        name="Admin User",
        email="admin@test.com",
        password=get_password_hash("adminpass"),
        active=True,
        is_admin=True,
        created_by=admin_id
    )
    db.add(admin_user)
    db.commit()
    token = create_access_token(data={"sub": str(admin_id)})
    return {"Authorization": f"Bearer {token}"}

def test_list_users_as_admin(client: TestClient, db):
    headers = get_admin_headers(client, db)
    
    client.post("/auth/register", json={
        "name": "Normal User",
        "email": "normal@test.com",
        "password": "123"
    })
    
    response = client.get("/users", headers=headers)
    
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 1

def test_list_users_unauthorized(client: TestClient):
    response = client.get("/users") 
    assert response.status_code == 401