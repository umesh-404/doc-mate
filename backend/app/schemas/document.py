"""Document schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import DocumentStatus, DocumentType


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    doc_type: DocumentType
    status: DocumentStatus
    filename: str | None = None
    content_type: str | None = None
    storage_key: str | None = None
    size_bytes: int | None = None
    confidence: float | None = None
    error_reason: str | None = None
    created_at: datetime
