"""Consultation-scribe schemas (contract v3).

Shapes deliberately echo the Summary snapshot the frontend already renders
(``{key, title, items}``) so the doctor's draft note and the patient snapshot
look like one product.

Note the section keys: ``subjective | objective | plan | follow_up | flags``.
There is intentionally **no assessment/diagnosis key** — the scribe records what
was said and proposes; the doctor concludes (PROJECT.md section 4).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.db.models import ClinicalItemKind, ConsultNoteStatus

SectionKey = Literal["subjective", "objective", "plan", "follow_up", "flags"]


class NoteItem(BaseModel):
    """One line of the draft note, lifted verbatim from the transcript."""

    text: str
    # True when the line was hedged/inaudible — shown as ⚠ needs verification.
    needs_verification: bool = False


class Section(BaseModel):
    key: SectionKey
    title: str
    items: list[NoteItem] = []


class ProposedItem(BaseModel):
    """A clinical fact the scribe *proposes*; nothing is stored until verified."""

    kind: ClinicalItemKind
    label: str
    value: str | None = None
    unit: str | None = None
    confidence: float | None = None
    needs_verification: bool = True


class ConsultNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    status: ConsultNoteStatus
    language: str
    confidence: float | None = None
    created_at: datetime


class ConsultNoteDetail(ConsultNoteRead):
    transcript: str | None = None
    # Contract field name is ``error``; the ORM column is ``error_reason``.
    error: str | None = None
    sections: list[Section] = []
    proposed_items: list[ProposedItem] = []


class ConsultVerifyRequest(BaseModel):
    """Body for POST /consult/{id}/verify.

    ``item_indexes`` indexes into ``proposed_items`` (omit to accept all).
    ``edits`` maps that same index (as a string key) to field overrides —
    ``{"0": {"label": "Metformin 500mg", "value": "1-0-1"}}`` — so a misheard
    dose is corrected by the doctor before it ever enters the record.
    """

    item_indexes: list[int] | None = None
    edits: dict[str, dict] | None = None
