"""Triage schemas — suggested OPD review priority (contract v3).

  QueueEntry   = {patient_id, patient_name, age?, sex?, level, score,
                  waiting_since?, top_reason?}
  TriageReason = {text, weight, citations:[Citation]}
  TriageRead   = {patient_id, level, score, reasons, computed_at, disclaimer}
  Citation     = {document_id, label}

``level`` is a *suggestion* for a clinician to confirm or override, never a
diagnosis (PROJECT.md section 4) — hence the mandatory ``disclaimer``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TriageLevel = Literal["emergency", "urgent", "routine"]


class Citation(BaseModel):
    document_id: uuid.UUID
    label: str


class TriageReason(BaseModel):
    """One contributing factor and the points it added to the score."""

    text: str
    weight: int
    citations: list[Citation] = []


class TriageRead(BaseModel):
    patient_id: uuid.UUID
    level: TriageLevel
    score: int
    reasons: list[TriageReason] = []
    computed_at: datetime
    # Plain-language statement that this is a suggestion, not a diagnosis.
    disclaimer: str


class QueueEntry(BaseModel):
    patient_id: uuid.UUID
    patient_name: str
    age: int | None = None
    sex: str | None = None
    level: TriageLevel
    score: int
    # Arrival-time proxy — see app.triage.queue for exactly what this is.
    waiting_since: datetime | None = None
    top_reason: str | None = None


class QueueCounts(BaseModel):
    emergency: int = 0
    urgent: int = 0
    routine: int = 0


class QueueRead(BaseModel):
    generated_at: datetime
    arrival_ordered: list[QueueEntry] = []
    priority_ordered: list[QueueEntry] = []
    counts: QueueCounts = QueueCounts()
    disclaimer: str = ""
