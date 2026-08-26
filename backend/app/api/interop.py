"""Interoperability routes: FHIR R4 export, mock ABHA lookup, medical coding.

Everything here is computed at request time from existing data — no new tables,
no persistence, no external/terminology-service calls (offline, stub-safe).
See PROJECT.md section 3 (India context) and section 9 (data model).

The FHIR export is an honest "ABDM-ready" demonstration: schema-plausible FHIR
R4 resources with ICD-11/NAMASTE codings where they map. The ABHA lookup is a
clearly-MOCK resolver, not real National Health Authority integration.

Router name: ``router`` (prefix ``/interop`` unset — paths are absolute per the
frontend contract; mount without an extra prefix).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coding import map_condition, search as coding_search
from app.core.security import get_current_user
from app.db.models import ClinicalItem, Document, Encounter, Patient
from app.db.session import get_db
from app.fhir.abha import mock_identity
from app.fhir.builder import build_patient_bundle
from app.schemas.coding import CodeOut, ItemCodes
from app.schemas.fhir import ABHALookup, FHIRBundle

router = APIRouter(tags=["interop"])

# Kinds that carry a resolvable medical code in the /codes projection.
_CODED_KINDS = {"condition", "observation", "procedure"}


def _load_patient(db: Session, patient_id: uuid.UUID) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    return patient


@router.get(
    "/patients/{patient_id}/fhir",
    response_model=FHIRBundle,
    dependencies=[Depends(get_current_user)],
)
def patient_fhir_bundle(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> FHIRBundle:
    """Export the patient's record as a FHIR R4 collection Bundle."""
    patient = _load_patient(db, patient_id)

    encounters = list(
        db.execute(
            select(Encounter).where(Encounter.patient_id == patient_id)
        ).scalars().all()
    )
    documents = list(
        db.execute(
            select(Document).where(Document.patient_id == patient_id)
        ).scalars().all()
    )
    items = list(
        db.execute(
            select(ClinicalItem).where(ClinicalItem.patient_id == patient_id)
        ).scalars().all()
    )

    bundle = build_patient_bundle(
        patient,
        encounters=encounters,
        documents=documents,
        clinical_items=items,
    )
    return FHIRBundle(**bundle)


@router.get(
    "/abha/lookup",
    response_model=ABHALookup,
    dependencies=[Depends(get_current_user)],
)
def abha_lookup(
    db: Annotated[Session, Depends(get_db)],
    abha_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> ABHALookup:
    """MOCK ABHA identity resolver (demo — not real NHA integration).

    If ``abha_id`` matches a seeded patient, returns their demographics;
    otherwise returns a deterministic plausible mock identity.
    """
    patient = db.execute(
        select(Patient).where(Patient.abha_id == abha_id)
    ).scalars().first()

    if patient is not None:
        return ABHALookup(
            abha_id=abha_id,
            name=patient.full_name,
            gender=_patient_gender(patient),
            year_of_birth=_patient_birth_year(patient),
            verified=True,
            source="mock",
        )

    return ABHALookup(**mock_identity(abha_id))  # type: ignore[arg-type]


@router.get(
    "/patients/{patient_id}/codes",
    response_model=list[ItemCodes],
    dependencies=[Depends(get_current_user)],
)
def patient_codes(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[ItemCodes]:
    """Resolve ICD-11/NAMASTE codes for the patient's coded clinical items."""
    _load_patient(db, patient_id)
    items = list(
        db.execute(
            select(ClinicalItem).where(ClinicalItem.patient_id == patient_id)
        ).scalars().all()
    )

    out: list[ItemCodes] = []
    for item in items:
        kind = getattr(item.kind, "value", item.kind)
        if str(kind) not in _CODED_KINDS:
            continue
        codes = map_condition(item.label or "")
        out.append(
            ItemCodes(
                item_label=item.label,
                kind=str(kind),
                codes=[CodeOut(**c.as_dict()) for c in codes],
            )
        )
    return out


@router.get(
    "/coding/search",
    response_model=list[CodeOut],
    dependencies=[Depends(get_current_user)],
)
def coding_search_endpoint(
    term: Annotated[str, Query(min_length=1, max_length=128)],
    system: Annotated[str | None, Query(pattern="^(icd11|namaste)$")] = None,
) -> list[CodeOut]:
    """Free-text search over the bundled ICD-11 / NAMASTE code lists."""
    codes = coding_search(term, system)
    return [CodeOut(**c.as_dict()) for c in codes]


# ---------------------------------------------------------------------------
# Demographic helpers (kept local; no new model logic)
# ---------------------------------------------------------------------------
_GENDER_NORM = {
    "m": "male", "male": "male",
    "f": "female", "female": "female",
    "o": "other", "other": "other",
}


def _patient_gender(patient: Patient) -> str:
    raw = patient.gender or patient.sex
    if not raw:
        return "unknown"
    return _GENDER_NORM.get(str(raw).strip().lower(), "unknown")


def _patient_birth_year(patient: Patient) -> int:
    if patient.date_of_birth is not None:
        return patient.date_of_birth.year
    if patient.age is not None:
        return datetime.now(timezone.utc).year - int(patient.age)
    return 0
