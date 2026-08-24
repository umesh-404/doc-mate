"""Patient schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PatientBase(BaseModel):
    full_name: str
    age: int | None = None
    sex: str | None = None
    abha_id: str | None = None
    phone: str | None = None
    preferred_language: str = "en"
    # Optional richer demographics (kept for FHIR-aligned data when available).
    gender: str | None = None
    date_of_birth: date | None = None
    demographics: dict | None = None


class PatientCreate(PatientBase):
    pass


class PatientRead(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
