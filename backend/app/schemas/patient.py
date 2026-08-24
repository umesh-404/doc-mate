"""Patient schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PatientBase(BaseModel):
    full_name: str
    abha_id: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    phone: str | None = None
    preferred_language: str = "en"
    demographics: dict | None = None


class PatientCreate(PatientBase):
    pass


class PatientRead(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
