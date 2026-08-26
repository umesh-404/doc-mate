"""Patient routes: create, list, get.

Creating a patient is a reception action; both roles may read patients.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._consent import consent_gate
from app.core.security import get_current_user, require_role
from app.db.models import AuditAction, Patient, UserRole
from app.db.session import get_db
from app.governance import audited
from app.schemas.patient import PatientCreate, PatientRead

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post(
    "",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.reception))],
)
def create_patient(
    payload: PatientCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Patient:
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get(
    "",
    response_model=list[PatientRead],
    dependencies=[Depends(get_current_user)],
)
def list_patients(
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[Patient]:
    stmt = (
        select(Patient)
        .order_by(Patient.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())


@router.get(
    "/{patient_id}",
    response_model=PatientRead,
    dependencies=[
        Depends(get_current_user),
        # Consent is evaluated before the access is logged, so a denial is
        # recorded as a denial rather than as a successful view.
        Depends(consent_gate(AuditAction.view_patient)),
        Depends(
            audited(
                AuditAction.view_patient,
                resource_type="patient",
                resource_param="patient_id",
            )
        ),
    ],
)
def get_patient(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    return patient
