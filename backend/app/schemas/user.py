"""User schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import UserRole


class UserBase(BaseModel):
    # Plain str (not EmailStr): demo/staff logins use short handles like
    # "reception@demo" that are intentionally not RFC-valid addresses.
    email: str
    full_name: str | None = None
    role: UserRole


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
