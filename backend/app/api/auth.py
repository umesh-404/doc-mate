"""Authentication routes.

POST /auth/login accepts either a JSON body ({email, password}) or a standard
OAuth2 form (username=email, password). GET /auth/me returns the current user.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    CurrentUser,
    create_access_token,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import TokenResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


async def _extract_credentials(request: Request) -> tuple[str, str]:
    """Read email + password from a JSON body or a form body."""
    content_type = request.headers.get("content-type", "")
    email: str | None = None
    password: str | None = None

    if content_type.startswith("application/json"):
        body = await request.json()
        email = body.get("email") or body.get("username")
        password = body.get("password")
    else:
        form = await request.form()
        email = form.get("email") or form.get("username")
        password = form.get("password")

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="email and password are required",
        )
    return str(email), str(password)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    email, password = await _extract_credentials(request)
    user = db.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()

    # Constant-ish behaviour: same error whether user missing or bad password.
    if user is None or not user.is_active or not verify_password(
        password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(user_id=str(user.id), role=user.role.value)
    return TokenResponse(access_token=token, role=user.role)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user
