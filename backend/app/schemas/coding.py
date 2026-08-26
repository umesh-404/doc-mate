"""Schemas for the medical-coding endpoints (ICD-11 / NAMASTE)."""

from __future__ import annotations

from pydantic import BaseModel


class CodeOut(BaseModel):
    """A single resolved medical code."""

    system: str  # "ICD-11" | "NAMASTE"
    code: str
    display: str


class ItemCodes(BaseModel):
    """Codes resolved for one clinical item (Condition/Observation)."""

    item_label: str
    kind: str  # ClinicalItemKind value, e.g. "condition"
    codes: list[CodeOut]
