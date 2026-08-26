"""Semantic search over one patient's indexed record (pgvector).

Makes the retrieval layer demonstrable: the same chunk index that feeds
narrative context into summary generation is queryable directly, so a doctor
can ask "what did the discharge summary say about follow-up?" and get the
source prose back with a resolvable citation.

Patient isolation is enforced in SQL inside
:func:`app.rag.retrieval.semantic_search` — a chunk belonging to another
patient can never be ranked or returned.

This is a POST, not a GET, on purpose. A clinician's search terms are patient
content ("chest pain since Tuesday"), and a query string lands in every HTTP
access log along the way — uvicorn's default among them. PROJECT.md section 4.6
forbids patient data in URLs or query strings, so the query travels in the
request body and never appears in a URL.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api._consent import consent_gate
from app.core.security import get_current_user
from app.db.models import AuditAction, Patient
from app.db.session import get_db
from app.governance import audited
from app.rag.retrieval import (
    SEARCH_DEFAULT_LIMIT,
    SEARCH_MAX_LIMIT,
    semantic_search,
)
from app.schemas.search import SearchHit, SearchRequest, SearchResponse

router = APIRouter(prefix="/patients", tags=["search"])


@router.post(
    "/{patient_id}/search",
    response_model=SearchResponse,
    dependencies=[
        Depends(get_current_user),
        Depends(consent_gate(AuditAction.view_patient)),
        Depends(audited(AuditAction.view_patient, resource_type="patient")),
    ],
)
def search_patient_record(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    payload: SearchRequest,
) -> SearchResponse:
    """Rank this patient's indexed text chunks against the supplied query."""
    if db.get(Patient, patient_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    limit = min(payload.limit or SEARCH_DEFAULT_LIMIT, SEARCH_MAX_LIMIT)
    hits = semantic_search(db, patient_id, payload.query, limit=limit)
    return SearchResponse(
        query=payload.query, results=[SearchHit(**h) for h in hits]
    )
