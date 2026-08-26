"""Clinical-safety routes.

Exposes an offline drug-drug interaction + drug-allergy check for a patient,
computed from that patient's *verified* medication and allergy clinical items
against the bundled reference dataset (:mod:`app.safety.interactions`). No
external API is called and no patient data leaves the system (PROJECT.md
sections 4, 5). Results are surfacing-only flags for a clinician to review —
never a diagnosis or a treatment recommendation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import ClinicalItem, ClinicalItemKind, Patient
from app.db.session import get_db
from app.safety.interactions import check_allergy_conflicts, check_interactions

router = APIRouter(prefix="/patients", tags=["safety"])


@router.get(
    "/{patient_id}/interactions",
    dependencies=[Depends(get_current_user)],
)
def get_interactions(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return drug-drug interactions and allergy conflicts for a patient.

    Only *verified* medication/allergy items are considered, so unconfirmed
    OCR extractions never drive a safety flag (PROJECT.md section 4,
    human-in-the-loop).
    """
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    stmt = (
        select(ClinicalItem)
        .where(ClinicalItem.patient_id == patient_id)
        .where(
            ClinicalItem.kind.in_(
                [ClinicalItemKind.medication, ClinicalItemKind.allergy]
            )
        )
        .where(ClinicalItem.verified.is_(True))
    )
    items = list(db.execute(stmt).scalars().all())

    med_labels = [
        it.label for it in items if it.kind == ClinicalItemKind.medication
    ]
    allergy_labels = [
        it.label for it in items if it.kind == ClinicalItemKind.allergy
    ]

    return {
        "checked_at": datetime.now(timezone.utc),
        "medications": [{"name": name, "rxcui": None} for name in med_labels],
        "interactions": check_interactions(med_labels),
        "allergy_conflicts": check_allergy_conflicts(med_labels, allergy_labels),
    }
