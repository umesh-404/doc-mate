"""SQLAlchemy 2.0 engine and session management.

The engine is created lazily on first use so importing the app (and starting
Uvicorn) never opens a database connection. This keeps startup fast and lets
the API boot even when Postgres is unreachable.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return the process-wide session factory, creating it on first call."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
