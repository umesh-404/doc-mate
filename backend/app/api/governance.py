"""Governance routes: patient consent + access audit trail (Contract v3).

Implements the DPDP Act 2023 story for the demo: explicit, scoped,
purpose-bound consent that can be revoked in real time, and an append-only
access log that shows a patient exactly who opened their record and why.

Nothing here returns patient content, so both roles may read the audit views.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Patient, User
from app.db.session import get_db
from app.governance.audit import (
    MAX_AUDIT_ROWS,
    get_patient_access_history,
    get_recent_access,
    iter_audit_entries,
)
from app.governance.consent import (
    get_latest_consent,
    grant_consent,
    revoke_consent,
)
from app.schemas.governance import (
    AuditListResponse,
    ConsentGrantRequest,
    ConsentRead,
    ConsentRevokeRequest,
)

router = APIRouter(tags=["governance"])


def _require_patient(db: Session, patient_id: uuid.UUID) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    return patient


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------
@router.post(
    "/patients/{patient_id}/consent",
    response_model=ConsentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_consent(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    payload: ConsentGrantRequest | None = Body(default=None),
) -> ConsentRead:
    """Record explicit patient consent. Supersedes any earlier active consent.

    Writes a ``consent_grant`` audit row.
    """
    _require_patient(db, patient_id)
    body = payload or ConsentGrantRequest()
    consent = grant_consent(
        db,
        patient_id,
        scope=body.scope,
        purpose=body.purpose,
        granted_by=user,
        expires_at=body.expires_at,
    )
    return ConsentRead.model_validate(consent)


@router.delete("/patients/{patient_id}/consent", response_model=ConsentRead)
def delete_consent(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    payload: ConsentRevokeRequest | None = Body(default=None),
    reason: str | None = Query(default=None, max_length=64),
) -> ConsentRead:
    """Revoke consent in real time. Writes a ``consent_revoke`` audit row.

    ``reason`` may be passed as a query parameter or in the body (some HTTP
    clients drop DELETE bodies). 404 when the patient has no consent on record.
    """
    _require_patient(db, patient_id)
    body_reason = payload.reason if payload else None
    consent = revoke_consent(
        db, patient_id, reason=body_reason or reason, actor=user
    )
    if consent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No consent on record for this patient",
        )
    return ConsentRead.model_validate(consent)


@router.get("/patients/{patient_id}/consent", response_model=ConsentRead | None)
def read_consent(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ConsentRead | None:
    """Return the patient's most recent consent record.

    **Contract choice:** returns HTTP 200 with a JSON ``null`` body when the
    patient has never had consent recorded (not 404), so the reception UI can
    render a "no consent yet" state without treating it as an error. A 404 here
    means the *patient* does not exist.
    """
    _require_patient(db, patient_id)
    consent = get_latest_consent(db, patient_id)
    return ConsentRead.model_validate(consent) if consent else None


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------
@router.get("/patients/{patient_id}/audit", response_model=AuditListResponse)
def read_patient_audit(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AuditListResponse:
    """Who accessed this patient's record, most recent first (max 200)."""
    _require_patient(db, patient_id)
    entries = get_patient_access_history(db, patient_id, limit=MAX_AUDIT_ROWS)
    return AuditListResponse(entries=list(iter_audit_entries(db, entries)))


@router.get("/audit/recent", response_model=AuditListResponse)
def read_recent_audit(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=MAX_AUDIT_ROWS),
) -> AuditListResponse:
    """Hospital-wide recent access, most recent first. Contains no patient content."""
    entries = get_recent_access(db, limit=limit)
    return AuditListResponse(entries=list(iter_audit_entries(db, entries)))
