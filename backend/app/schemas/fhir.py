"""Schemas for the interoperability endpoints (FHIR export + mock ABHA).

The FHIR Bundle is emitted as free-form JSON (a FHIR R4 Bundle is deeply nested
and versioned; validating it with Pydantic would add little for a demo). We type
the envelope loosely and let :mod:`app.fhir.builder` shape the resources.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FHIRBundle(BaseModel):
    """A FHIR R4 Bundle (type ``collection``). Resources are open dicts."""

    resourceType: str = "Bundle"
    type: str = "collection"
    timestamp: str | None = None
    total: int = 0
    entry: list[dict[str, Any]] = Field(default_factory=list)


class ABHALookup(BaseModel):
    """Result of the MOCK ABHA identity resolver (not real NHA integration)."""

    abha_id: str
    name: str
    gender: str
    year_of_birth: int
    verified: bool = True
    source: str = "mock"
