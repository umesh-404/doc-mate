"""Declarative base and metadata aggregation point.

Alembic and table-creation code import ``Base`` from here. Importing this
module also imports every model module so that ``Base.metadata`` is fully
populated (needed for autogenerate and ``create_all``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class TimestampMixin:
    """Adds created/updated timestamps managed by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Import models so their tables register on Base.metadata. Kept at the bottom
# to avoid circular imports. noqa: E402/F401 are intentional.
from app.db import models  # noqa: E402,F401
