from sqlalchemy.orm import Session
from uuid import uuid4
from app.models.user import User
from app.core.security import get_password_hash

def test_create_user_db(db: Session):
    user_id = uuid4()
    email = "crud_test@example.com"
    password = "password123"
    
    new_user = User(
        id=user_id,
        name="Test CRUD User",
        email=email,
        password=get_password_hash(password),
        active=True,
        created_by=user_id
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    retrieved_user = db.query(User).filter(User.email == email).first()
    assert retrieved_user is not None
    assert retrieved_user.id == user_id
    assert retrieved_user.name == "Test CRUD User"