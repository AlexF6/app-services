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

    # Respect explicit sslmode in the URL if already present
    has_sslmode_in_url = "sslmode=" in db_url

    is_local = (
        "localhost" in db_url
        or "127.0.0.1" in db_url
        or "0.0.0.0" in db_url
    )

    if not is_local and not has_sslmode_in_url:
        # Cloud DBs typically require SSL
        args["sslmode"] = "require"
    elif is_local and not has_sslmode_in_url:
        # Local DBs commonly run without SSL
        args["sslmode"] = "disable"

    # TCP keepalive knobs (psycopg2 forwards these to libpq)
    # These help keep long-lived idle connections from being dropped silently.
    args.update(
        {
            "keepalives": 1,
            "keepalives_idle": 30,      # seconds before probing idle
            "keepalives_interval": 10,  # seconds between probes
            "keepalives_count": 5,      # failed probes before giving up
        }
    )

    return args


# --- SQLAlchemy Base class ---
class Base(DeclarativeBase):
    pass


# --- Engine / Session setup ---
# Notes:
# - pool_pre_ping: validates a connection from the pool before using it (fixes dead sockets)
# - pool_recycle: proactively refresh connections before servers/proxies kill them (tune as needed)
# - pool_size / max_overflow: keep modest defaults; adjust for your traffic
CONNECT_ARGS = _build_connect_args(settings.DATABASE_URL)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,      # adjust to be lower than your provider's idle timeout (e.g., 300–600s)
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


# --- FastAPI dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
