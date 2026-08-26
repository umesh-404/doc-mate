"""Schemas for patient-scoped semantic search over the pgvector chunk index."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Search terms travel in the body, never a query string.

    A clinician's query is patient content, and PROJECT.md section 4.6 forbids
    patient data in URLs — a query string would be copied into every HTTP
    access log on the path.
    """

    query: str = Field(min_length=1, max_length=512)
    limit: int | None = Field(default=None, ge=1)


class SearchHit(BaseModel):
    """One retrieved chunk, carrying everything needed to cite it."""

    text: str
    document_id: uuid.UUID
    doc_type: str | None = None
    date: str | None = None
    citation_label: str = "Source"
    #: Cosine similarity in [-1, 1]; ``None`` when the result was not ranked.
    score: float | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit] = Field(default_factory=list)
