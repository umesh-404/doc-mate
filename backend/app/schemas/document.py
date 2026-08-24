"""Document schemas.

``DocumentRead`` matches the shared API contract exactly; ``DocumentDetail``
extends it with the extracted text, an error reason, and the structured
clinical items proposed for reception verification.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type, datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import ClinicalItemKind, DocumentStatus, DocumentType


class ClinicalItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: ClinicalItemKind
    label: str
    value: str | None = None
    unit: str | None = None
    # Contract field name is ``date``; the ORM column is ``effective_date``.
    date: date_type | None = None
    confidence: float | None = None
    verified: bool
    source_document_id: uuid.UUID

    @classmethod
    def from_orm_item(cls, item) -> "ClinicalItemRead":
        return cls(
            id=item.id,
            kind=item.kind,
            label=item.label,
            value=item.value,
            unit=item.unit,
            date=item.effective_date,
            confidence=item.confidence,
            verified=item.verified,
            source_document_id=item.source_document_id,
        )


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    doc_type: DocumentType
    filename: str | None = None
    status: DocumentStatus
    confidence: float | None = None
    created_at: datetime


class DocumentDetail(DocumentRead):
    extracted_text: str | None = None
    # Contract field name is ``error``; the ORM column is ``error_reason``.
    error: str | None = None
    items: list[ClinicalItemRead] = []


class VerifyRequest(BaseModel):
    """Body for POST /documents/{id}/verify. Omit ``item_ids`` to verify all."""

    item_ids: list[uuid.UUID] | None = None
