from fastapi.testclient import TestClient

def test_register_user(client: TestClient):
    payload = {
        "name": "Juan Perez",
        "email": "juan@test.com",
        "password": "securepassword",
    }
    
    response = client.post("/auth/register", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert "id" in data

def test_login_user(client: TestClient):
    register_payload = {
        "name": "Login User",
        "email": "login@test.com",
        "password": "password123"
    }
    client.post("/auth/register", json=register_payload)
    
    login_data = {
        "username": "login@test.com",
        "password": "password123"
    }
    
    response = client.post("/auth/token", data=login_data)
    
    assert response.status_code == 200
    assert "message" in response.json()