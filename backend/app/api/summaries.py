"""Summary routes: generate and fetch a patient's citation-backed snapshot.

Generation is kicked off in the background so the request returns fast
(PROJECT.md section 6b). The doctor UI polls GET until a summary exists.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._consent import consent_gate
from app.core.security import get_current_user
from app.db.models import AuditAction, Patient, Summary
from app.db.session import get_db, get_sessionmaker
from app.governance import audited
from app.rag.summary import build_summary_read, generate_patient_summary
from app.schemas.summary import SummaryGenerateResponse, SummaryRead

router = APIRouter(prefix="/patients", tags=["summaries"])


def _run_summary(patient_id: uuid.UUID, language: str | None) -> None:
    """Background job: generate a summary using its own DB session."""
    session = get_sessionmaker()()
    try:
        generate_patient_summary(session, patient_id, language)
    finally:
        session.close()


@router.post(
    "/{patient_id}/summary",
    response_model=SummaryGenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(get_current_user),
        Depends(
            audited(AuditAction.generate_summary, resource_type="summary")
        ),
    ],
)
def create_summary(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> SummaryGenerateResponse:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    background_tasks.add_task(_run_summary, patient_id, patient.preferred_language)
    return SummaryGenerateResponse(status="generating")


@router.get(
    "/{patient_id}/summary",
    response_model=SummaryRead,
    dependencies=[
        Depends(get_current_user),
        Depends(consent_gate(AuditAction.view_summary)),
        Depends(audited(AuditAction.view_summary, resource_type="summary")),
    ],
)
def get_summary(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> SummaryRead:
    stmt = (
        select(Summary)
        .where(Summary.patient_id == patient_id)
        .order_by(Summary.created_at.desc())
        .limit(1)
    )
    summary = db.execute(stmt).scalars().first()
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No summary yet"
        )
    return build_summary_read(summary)
