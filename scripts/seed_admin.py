import uuid
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import User
from app.core.config import settings

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def run():
    db: Session = SessionLocal()
    admin_id = uuid.uuid4()
    admin = User(
        id=admin_id,
        name="Admin",
        email=settings.ADMIN_EMAIL,
        password=pwd.hash(settings.ADMIN_PASS),
        active=True,
        is_admin=True,
        created_by=admin_id,
    )
    db.add(admin)
    db.commit()
    print(f"Admin created with email: {admin.email} and id: {admin.id}")


if __name__ == "__main__":
    run()
