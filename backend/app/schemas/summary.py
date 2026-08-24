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


class Section(BaseModel):
    key: SectionKey
    title: str
    items: list[SummaryItem] = []


class SummaryRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    language: str
    generated_at: datetime
    sections: list[Section] = []


class SummaryGenerateResponse(BaseModel):
    status: Literal["generating", "ready"]
    summary_id: uuid.UUID | None = None
