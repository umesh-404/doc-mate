"""Auth request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr

from app.db.models import UserRole


class LoginRequest(BaseModel):
    """JSON login body. Form logins are also accepted by the endpoint."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
