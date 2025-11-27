# app/core/database.py
from __future__ import annotations

from typing import Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


def _build_connect_args(db_url: str) -> Dict[str, object]:
    """
    Build psycopg2 connect args:
    - Force SSL when not connecting to localhost (unless the URL already specifies sslmode)
    - Enable TCP keepalives to prevent idle connections from being killed by proxies/NAT
    """
    args: Dict[str, object] = {}

    has_sslmode_in_url = "sslmode=" in db_url

    is_local = (
        "localhost" in db_url
        or "127.0.0.1" in db_url
        or "0.0.0.0" in db_url
    )

    if not is_local and not has_sslmode_in_url:
        args["sslmode"] = "require"
    elif is_local and not has_sslmode_in_url:
        args["sslmode"] = "disable"

    args.update(
        {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    )

    return args


class Base(DeclarativeBase):
    pass


CONNECT_ARGS = _build_connect_args(settings.DATABASE_URL)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,
    pool_size=5,
    max_overflow=10,
    connect_args=CONNECT_ARGS,
    # echo=settings.DEBUG if you expose DEBUG in settings
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
