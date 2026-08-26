"""Build the OPD waiting queue, ordered by suggested review priority.

Computed entirely at request time from the existing tables (Patient, Encounter,
Document, ClinicalItem) — triage adds no tables, no columns, and no migrations,
so a suggestion is never stale and never becomes a stored clinical assertion.

Arrival-time proxy
------------------
There is no dedicated "checked in at" column in the schema today, so
``waiting_since`` uses, in order:

1. the patient's latest ``Encounter.occurred_at``,
2. else that encounter's ``created_at`` (row insert time),
3. else ``Patient.created_at``.

This is a documented proxy, not a real intake timestamp: for a walk-in
registered at the desk it is accurate to when the record was created, but for a
patient whose encounter was back-dated it is not a wait time. The UI should
label it as "record opened", and a real deployment should capture check-in
explicitly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, Encounter, Patient
from app.rag.retrieval import gather_context
from app.triage.scoring import TriageScore, score_patient

# Ordering rank for the priority view (highest urgency first).
_LEVEL_RANK = {"emergency": 0, "urgent": 1, "routine": 2}


def _latest_encounter(db: Session, patient_id: uuid.UUID) -> Encounter | None:
    stmt = (
        select(Encounter)
        .where(Encounter.patient_id == patient_id)
        .order_by(
            Encounter.occurred_at.desc().nullslast(),
            Encounter.created_at.desc(),
        )
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _waiting_since(
    patient: Patient, encounter: Encounter | None
) -> datetime | None:
    """Arrival-time proxy — see the module docstring."""
    if encounter is not None:
        return encounter.occurred_at or encounter.created_at
    return getattr(patient, "created_at", None)


def _documents_for(db: Session, patient_id: uuid.UUID) -> list[Document]:
    stmt = select(Document).where(Document.patient_id == patient_id)
    return list(db.execute(stmt).scalars().all())


def triage_patient(db: Session, patient: Patient) -> tuple[TriageScore, dict]:
    """Score one patient and return the score plus its queue metadata."""
    encounter = _latest_encounter(db, patient.id)
    facts = gather_context(db, patient.id)
    documents = _documents_for(db, patient.id)
    score = score_patient(
        facts,
        patient,
        documents=documents,
        complaint=encounter.reason if encounter is not None else None,
    )
    meta = {
        "waiting_since": _waiting_since(patient, encounter),
        "complaint": encounter.reason if encounter is not None else None,
    }
    return score, meta


def _entry(patient: Patient, score: TriageScore, meta: dict) -> dict:
    return {
        "patient_id": patient.id,
        "patient_name": patient.full_name,
        "age": patient.age,
        "sex": patient.sex or patient.gender,
        "level": score.level,
        "score": score.score,
        "waiting_since": meta.get("waiting_since"),
        "top_reason": score.top_reason,
    }


def build_queue(db: Session, limit: int = 50) -> dict:
    """Return the waiting list in both arrival order and suggested order.

    The two orderings are returned side by side on purpose: the UI shows what
    the queue *is* next to what triage *suggests*, so the difference is visible
    and a human stays in control of the actual call order.
    """
    limit = max(1, min(int(limit), 200))
    patients = list(
        db.execute(select(Patient).order_by(Patient.created_at.asc())).scalars()
    )

    entries: list[dict] = []
    for patient in patients:
        score, meta = triage_patient(db, patient)
        entries.append(_entry(patient, score, meta))

    _far_past = datetime.min.replace(tzinfo=timezone.utc)

    def _arrival_key(entry: dict):
        waiting = entry.get("waiting_since")
        if waiting is None:
            return _far_past
        if waiting.tzinfo is None:
            return waiting.replace(tzinfo=timezone.utc)
        return waiting

    arrival_ordered = sorted(entries, key=_arrival_key)[:limit]
    priority_ordered = sorted(
        entries,
        key=lambda e: (
            _LEVEL_RANK.get(e["level"], 9),
            -e["score"],
            _arrival_key(e),
        ),
    )[:limit]

    counts = {"emergency": 0, "urgent": 0, "routine": 0}
    for entry in entries:
        if entry["level"] in counts:
            counts[entry["level"]] += 1

    return {
        "generated_at": datetime.now(timezone.utc),
        "arrival_ordered": arrival_ordered,
        "priority_ordered": priority_ordered,
        "counts": counts,
    }
