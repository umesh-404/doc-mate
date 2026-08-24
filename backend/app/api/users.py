"""User routes (optional/admin-ish helpers).

Currently exposes a listing restricted to doctors. User creation for the demo
is handled by scripts/seed.py; add a protected create endpoint here later if
needed.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.models import User, UserRole
from app.db.session import get_db
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=list[UserRead],
    dependencies=[Depends(require_role(UserRole.doctor))],
)
def list_users(db: Annotated[Session, Depends(get_db)]) -> list[User]:
    return list(db.execute(select(User).order_by(User.created_at)).scalars().all())
