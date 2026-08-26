"""Summary schemas — the doctor's citation-backed patient snapshot.

Matches the shared API contract:
  Summary  = {id, patient_id, language, generated_at, sections:[Section]}
  Section  = {key, title, items:[SummaryItem]}
  SummaryItem = {text, severity?, trend?, confidence?, verified?,
                 citations:[Citation]}
  Citation = {document_id, label}
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SectionKey = Literal[
    "complaint",
    "problems",
    "allergies",
    "medications",
    "labs",
    "encounters",
    "flags",
]


class Citation(BaseModel):
    document_id: uuid.UUID
    label: str


class SummaryItem(BaseModel):
    text: str
    severity: Literal["high", "med", "low"] | None = None
    trend: Literal["up", "down", "flat"] | None = None
    confidence: float | None = None
    verified: bool | None = None
    citations: list[Citation] = []
    # Clinical-safety grounding (app.safety.grounding). Defaults keep older
    # callers/tests working: an item is assumed grounded unless flagged.
    grounded: bool = True
    grounding_note: str | None = None


class Section(BaseModel):
    key: SectionKey
    title: str
    items: list[SummaryItem] = []


class Grounding(BaseModel):
    """Faithfulness signal for a whole summary (see app.safety.grounding)."""

    score: float = 1.0  # fraction of non-flags items supported by their source
    method: str = "lexical+numeric overlap v1"
    unsupported_count: int = 0


class Alert(BaseModel):
    """A neutral, surfacing-only clinical flag — never a diagnosis."""

    level: Literal["critical", "warning", "info"]
    kind: Literal["allergy", "interaction", "abnormal_lab", "missing_data"]
    text: str
    citations: list[Citation] = []


class SummaryRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    language: str
    generated_at: datetime
    sections: list[Section] = []
    # Clinical-safety additions. Optional with safe defaults so existing
    # callers that don't populate them keep working.
    grounding: Grounding = Grounding()
    alerts: list[Alert] = []


class SummaryGenerateResponse(BaseModel):
    status: Literal["generating", "ready"]
    summary_id: uuid.UUID | None = None
