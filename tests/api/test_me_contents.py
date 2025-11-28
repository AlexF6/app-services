from fastapi.testclient import TestClient
from uuid import uuid4

from app.models.user import User
from app.models.content import Content
from app.core.security import get_password_hash, create_access_token


def get_user_headers(client: TestClient, db):
    """
    Usuario consistente para /me/contents. Lo reutilizamos si ya existe.
    """
    existing_user = db.query(User).filter(User.email == "user_me@test.com").first()

    if existing_user:
        user = existing_user
    else:
        user_id = uuid4()
        user = User(
            id=user_id,
            name="Normal User",
            email="user_me@test.com",
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
    return {"Authorization": f"Bearer {token}"}


def create_dummy_content(db):
    """
    El contenido debe tener created_by apuntando a un User válido.
    Usamos el mismo 'user_me@test.com' que en get_user_headers.
    """
    user = db.query(User).filter(User.email == "user_me@test.com").first()
    if not user:
        user_id = uuid4()
        user = User(
            id=user_id,
            name="Normal User",
            email="user_me@test.com",
            password=get_password_hash("user123"),
            active=True,
            is_admin=False,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    content_id = uuid4()
    content = Content(
        id=content_id,
        title="Public Content",
        type="MOVIE",
        description="For everyone",
        release_year=2024,
        duration_seconds=3600,
        age_rating="PG",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(content)
    db.commit()
    return content_id


def test_list_my_contents(client: TestClient, db):
    headers = get_user_headers(client, db)
    create_dummy_content(db)

    response = client.get("/me/contents", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(c["title"] == "Public Content" for c in data)


def test_get_specific_content_details(client: TestClient, db):
    headers = get_user_headers(client, db)
    content_id = create_dummy_content(db)

    response = client.get(f"/me/contents/{content_id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(content_id)
    assert data["title"] == "Public Content"


def test_unauthorized_access(client: TestClient):
    response = client.get("/me/contents")
    assert response.status_code == 401
