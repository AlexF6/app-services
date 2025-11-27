# tests/conftest.py
import pytest
import re
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, get_db

from app.models.user import User
from app.models.profile import Profile
from app.models.subscription import Subscription
from app.models.plan import Plan
from app.models.content import Content

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

@event.listens_for(engine, "before_cursor_execute", retval=True)
def fix_sql_for_sqlite(conn, cursor, statement, parameters, context, executemany):
    """
    Esta función intercepta el SQL antes de ejecutarse en SQLite y:
    1. Elimina los casteos de tipo Postgres (ej: ::subscription_status)
    2. Reemplaza gen_random_uuid() por NULL (SQLite no lo soporta, Python debe generar el ID)
    3. Reemplaza true/false por 1/0 si es necesario (aunque SQLAlchemy suele manejar esto)
    """
    statement = re.sub(r"::[\w_]+", "", statement)
    statement = statement.replace("gen_random_uuid()", "null")
    return statement, parameters

# ---------------------------------------------------

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as c:
        yield c
    
    app.dependency_overrides.clear()
