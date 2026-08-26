"""OPD triage + queue-intelligence routes.

Serves a *suggested* review priority for the waiting list, computed offline and
deterministically from records already ingested (:mod:`app.triage`). Nothing
here is a diagnosis and nothing here decides who is seen: the response carries
both the arrival order and the suggested order so a triage nurse or doctor can
see the difference and override it (PROJECT.md section 4).

Nothing is persisted — the score is recomputed per request, so a suggestion can
never go stale or harden into a stored clinical assertion.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Patient
from app.db.session import get_db
from app.schemas.triage import QueueRead, TriageRead
from app.triage.queue import build_queue, triage_patient
from app.triage.scoring import TRIAGE_DISCLAIMER

router = APIRouter(tags=["triage"])


@router.get(
    "/triage/queue",
    response_model=QueueRead,
    dependencies=[Depends(get_current_user)],
)
def get_triage_queue(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> QueueRead:
    """Return the waiting list in arrival order and in suggested review order."""
    queue = build_queue(db, limit=limit)
    queue["disclaimer"] = TRIAGE_DISCLAIMER
    return QueueRead(**queue)


@router.get(
    "/patients/{patient_id}/triage",
    response_model=TriageRead,
    dependencies=[Depends(get_current_user)],
)
def get_patient_triage(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> TriageRead:
    """Return one patient's suggested review priority and its cited reasons."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    score, _meta = triage_patient(db, patient)
    return TriageRead(patient_id=patient.id, **score.to_dict())
