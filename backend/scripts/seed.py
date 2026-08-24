"""Seed demo users. Idempotent — safe to run repeatedly.

Creates:
  reception@demo / demo1234  (role: reception)
  doctor@demo    / demo1234  (role: doctor)

Run from the backend/ directory after migrations:
    python -m scripts.seed
Requires a reachable database (DATABASE_URL).
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import User, UserRole
from app.db.session import get_sessionmaker

DEMO_USERS = [
    {
        "email": "reception@demo",
        "full_name": "Reception Demo",
        "role": UserRole.reception,
        "password": "demo1234",
    },
    {
        "email": "doctor@demo",
        "full_name": "Doctor Demo",
        "role": UserRole.doctor,
        "password": "demo1234",
    },
]


def seed() -> None:
    session = get_sessionmaker()()
    try:
        for spec in DEMO_USERS:
            existing = session.execute(
                select(User).where(User.email == spec["email"])
            ).scalar_one_or_none()
            if existing is not None:
                print(f"exists: {spec['email']} ({spec['role'].value})")
                continue
            user = User(
                email=spec["email"],
                full_name=spec["full_name"],
                role=spec["role"],
                hashed_password=hash_password(spec["password"]),
                is_active=True,
            )
            session.add(user)
            print(f"created: {spec['email']} ({spec['role'].value})")
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    seed()
