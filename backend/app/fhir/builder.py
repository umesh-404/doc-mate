"""Build a FHIR R4 Bundle for a patient from internal ORM/dict data.

Bundles are computed at request time from existing records — no new DB columns,
no persistence. The output is schema-plausible FHIR R4 (correct ``resourceType``
and the fields a reader expects), not a validator-clean instance: India-profile
(ABDM) extensions are intentionally omitted and terminology bindings are light.

Design notes:
- Resource ids are stable and derived from the source row's UUID so the same
  patient always produces the same bundle (good for demos and diffs).
- References wire up via ``{ResourceType}/{id}`` (e.g. Observation.subject ->
  ``Patient/{id}``), so a judge can follow the graph.
- Conditions (and observations, where sensible) carry ICD-11 / NAMASTE codings
  resolved offline via :mod:`app.coding`. If no code maps, ``code.text`` is used
  with no fabricated ``coding`` (PROJECT.md section 4).

The builder accepts either SQLAlchemy model instances or plain mappings, so it
is unit-testable without a database (see ``tests/test_interop.py``).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.coding import Code, map_condition
from app.fhir.mapping import citation_prefix_for, fhir_resource_for

# ABHA identifier system (ABDM patient health id namespace).
ABHA_SYSTEM = "https://healthid.ndhm.gov.in"
# Internal Doc-mate id namespaces (demo).
INTERNAL_PATIENT_SYSTEM = "urn:docmate:patient"

# FHIR AdministrativeGender value set.
_GENDER_MAP = {
    "m": "male", "male": "male",
    "f": "female", "female": "female",
    "o": "other", "other": "other",
    "u": "unknown", "unknown": "unknown",
}

# ClinicalItemKind -> Observation category code (rough demo mapping).
_OBS_CATEGORY = "laboratory"


def _get(obj: Any, name: str, default: Any = None) -> Any:
    """Attribute-or-key accessor so models and dicts both work."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _id(obj: Any) -> str:
    """Stable string id for a row (its UUID/id, stringified)."""
    return str(_get(obj, "id", ""))


def _enum_value(v: Any) -> str | None:
    """Normalize an Enum/str field to its plain string value."""
    if v is None:
        return None
    return getattr(v, "value", v)


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def _map_gender(patient: Any) -> str | None:
    raw = _get(patient, "gender") or _get(patient, "sex")
    if not raw:
        return None
    return _GENDER_MAP.get(str(raw).strip().lower(), "unknown")


# ---------------------------------------------------------------------------
# Resource builders
# ---------------------------------------------------------------------------
def build_patient(patient: Any) -> dict[str, Any]:
    identifiers: list[dict[str, Any]] = []
    abha = _get(patient, "abha_id")
    if abha:
        identifiers.append(
            {
                "system": ABHA_SYSTEM,
                "value": abha,
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "NI",
                            "display": "National unique individual identifier",
                        }
                    ],
                    "text": "ABHA Number",
                },
            }
        )
    identifiers.append(
        {"system": INTERNAL_PATIENT_SYSTEM, "value": _id(patient)}
    )

    resource: dict[str, Any] = {
        "resourceType": "Patient",
        "id": _id(patient),
        "identifier": identifiers,
        "name": [{"text": _get(patient, "full_name")}],
    }
    gender = _map_gender(patient)
    if gender:
        resource["gender"] = gender
    dob = _iso(_get(patient, "date_of_birth"))
    if dob:
        resource["birthDate"] = dob
    phone = _get(patient, "phone")
    if phone:
        resource["telecom"] = [{"system": "phone", "value": phone}]
    lang = _get(patient, "preferred_language")
    if lang:
        resource["communication"] = [
            {
                "language": {"coding": [{"system": "urn:ietf:bcp:47", "code": lang}]},
                "preferred": True,
            }
        ]
    return resource


def build_encounter(encounter: Any, patient_id: str) -> dict[str, Any]:
    status = _get(encounter, "status") or "unknown"
    # FHIR Encounter.status value set differs from our internal strings.
    status_map = {
        "in_progress": "in-progress",
        "in-progress": "in-progress",
        "finished": "finished",
        "completed": "finished",
        "planned": "planned",
        "cancelled": "cancelled",
    }
    resource: dict[str, Any] = {
        "resourceType": "Encounter",
        "id": _id(encounter),
        "status": status_map.get(str(status), "unknown"),
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory",
        },
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    reason = _get(encounter, "reason")
    if reason:
        resource["reasonCode"] = [{"text": reason}]
    occurred = _iso(_get(encounter, "occurred_at"))
    if occurred:
        resource["period"] = {"start": occurred}
    return resource


def build_document_reference(
    doc: Any, patient_id: str, encounter_id: str | None
) -> dict[str, Any]:
    doc_type = _enum_value(_get(doc, "doc_type")) or "other"
    status = _enum_value(_get(doc, "status")) or "uploaded"
    # Map internal document status to FHIR DocumentReference.status.
    fhir_status = "current" if status != "failed" else "entered-in-error"
    resource: dict[str, Any] = {
        "resourceType": "DocumentReference",
        "id": _id(doc),
        "status": fhir_status,
        "type": {"text": citation_prefix_for(doc_type)},
        "category": [{"text": doc_type}],
        "subject": {"reference": f"Patient/{patient_id}"},
        "description": _get(doc, "filename") or doc_type,
    }
    created = _iso(_get(doc, "created_at"))
    if created:
        resource["date"] = created
    content: dict[str, Any] = {"attachment": {}}
    ctype = _get(doc, "content_type")
    if ctype:
        content["attachment"]["contentType"] = ctype
    fname = _get(doc, "filename")
    if fname:
        content["attachment"]["title"] = fname
    resource["content"] = [content]
    if encounter_id:
        resource["context"] = {"encounter": [{"reference": f"Encounter/{encounter_id}"}]}
    return resource


def _codeable_from_codes(text: str, codes: list[Code]) -> dict[str, Any]:
    cc: dict[str, Any] = {"text": text}
    if codes:
        cc["coding"] = [
            {"system": c.system_uri(), "code": c.code, "display": c.display}
            for c in codes
        ]
    return cc


def build_condition(item: Any, patient_id: str) -> dict[str, Any]:
    label = _get(item, "label") or ""
    codes = map_condition(label)
    resource: dict[str, Any] = {
        "resourceType": "Condition",
        "id": _id(item),
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": (
                        "http://terminology.hl7.org/CodeSystem/"
                        "condition-ver-status"
                    ),
                    "code": "confirmed" if _get(item, "verified") else "provisional",
                }
            ]
        },
        "code": _codeable_from_codes(label, codes),
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    onset = _iso(_get(item, "effective_date"))
    if onset:
        resource["onsetDateTime"] = onset
    src = _get(item, "source_document_id")
    if src:
        resource["evidence"] = [
            {"detail": [{"reference": f"DocumentReference/{src}"}]}
        ]
    return resource


def build_observation(item: Any, patient_id: str) -> dict[str, Any]:
    label = _get(item, "label") or ""
    # Observations can also carry a code where the label maps (e.g. HbA1c).
    codes = map_condition(label)
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": _id(item),
        "status": "final" if _get(item, "verified") else "preliminary",
        "category": [
            {
                "coding": [
                    {
                        "system": (
                            "http://terminology.hl7.org/CodeSystem/"
                            "observation-category"
                        ),
                        "code": _OBS_CATEGORY,
                    }
                ]
            }
        ],
        "code": _codeable_from_codes(label, codes),
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    value = _get(item, "value")
    unit = _get(item, "unit")
    if value is not None and value != "":
        # Prefer a numeric quantity when the value parses as a number.
        num = _to_number(value)
        if num is not None:
            q: dict[str, Any] = {"value": num}
            if unit:
                q["unit"] = unit
            resource["valueQuantity"] = q
        else:
            resource["valueString"] = f"{value} {unit}".strip() if unit else str(value)
    eff = _iso(_get(item, "effective_date"))
    if eff:
        resource["effectiveDateTime"] = eff
    src = _get(item, "source_document_id")
    if src:
        resource["derivedFrom"] = [{"reference": f"DocumentReference/{src}"}]
    return resource


def build_medication_request(item: Any, patient_id: str) -> dict[str, Any]:
    label = _get(item, "label") or ""
    resource: dict[str, Any] = {
        "resourceType": "MedicationRequest",
        "id": _id(item),
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {"text": label},
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    value = _get(item, "value")
    if value:
        # Dosage timing string, e.g. "1-0-1"; kept as free text (demo).
        resource["dosageInstruction"] = [{"text": str(value)}]
    authored = _iso(_get(item, "effective_date"))
    if authored:
        resource["authoredOn"] = authored
    src = _get(item, "source_document_id")
    if src:
        resource["supportingInformation"] = [
            {"reference": f"DocumentReference/{src}"}
        ]
    return resource


def build_allergy_intolerance(item: Any, patient_id: str) -> dict[str, Any]:
    label = _get(item, "label") or ""
    resource: dict[str, Any] = {
        "resourceType": "AllergyIntolerance",
        "id": _id(item),
        "clinicalStatus": {
            "coding": [
                {
                    "system": (
                        "http://terminology.hl7.org/CodeSystem/"
                        "allergyintolerance-clinical"
                    ),
                    "code": "active",
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": (
                        "http://terminology.hl7.org/CodeSystem/"
                        "allergyintolerance-verification"
                    ),
                    "code": "confirmed" if _get(item, "verified") else "unconfirmed",
                }
            ]
        },
        "code": {"text": label},
        "patient": {"reference": f"Patient/{patient_id}"},
    }
    recorded = _iso(_get(item, "effective_date"))
    if recorded:
        resource["recordedDate"] = recorded
    return resource


def build_procedure(item: Any, patient_id: str) -> dict[str, Any]:
    label = _get(item, "label") or ""
    codes = map_condition(label)
    resource: dict[str, Any] = {
        "resourceType": "Procedure",
        "id": _id(item),
        "status": "completed",
        "code": _codeable_from_codes(label, codes),
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    performed = _iso(_get(item, "effective_date"))
    if performed:
        resource["performedDateTime"] = performed
    src = _get(item, "source_document_id")
    if src:
        resource["report"] = [{"reference": f"DocumentReference/{src}"}]
    return resource


# ClinicalItemKind (string value) -> builder function.
_ITEM_BUILDERS = {
    "condition": build_condition,
    "observation": build_observation,
    "medication": build_medication_request,
    "allergy": build_allergy_intolerance,
    "procedure": build_procedure,
}


def build_clinical_item(item: Any, patient_id: str) -> dict[str, Any] | None:
    """Dispatch a ClinicalItem to the right resource builder by kind."""
    kind = _enum_value(_get(item, "kind"))
    builder = _ITEM_BUILDERS.get(str(kind))
    if builder is None:
        return None
    return builder(item, patient_id)


def _to_number(value: Any) -> float | int | None:
    try:
        f = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else f


# ---------------------------------------------------------------------------
# Bundle assembly
# ---------------------------------------------------------------------------
def build_patient_bundle(
    patient: Any,
    encounters: list[Any] | None = None,
    documents: list[Any] | None = None,
    clinical_items: list[Any] | None = None,
) -> dict[str, Any]:
    """Assemble a FHIR R4 collection Bundle from a patient's records.

    All arguments accept ORM instances or plain dicts. Only ``patient`` is
    required; the rest default to empty. The bundle is of type ``collection``
    (a static snapshot for interoperability/export, not a transaction).
    """
    patient_id = _id(patient)
    entries: list[dict[str, Any]] = []

    def add(resource: dict[str, Any]) -> None:
        rid = resource.get("id", "")
        entry: dict[str, Any] = {"resource": resource}
        if rid:
            # A stable fullUrl lets references (Type/id) resolve within the bundle.
            entry["fullUrl"] = f"{resource['resourceType']}/{rid}"
        entries.append(entry)

    add(build_patient(patient))

    # Which encounter a document belongs to (for context.encounter linking).
    for enc in encounters or []:
        add(build_encounter(enc, patient_id))

    for doc in documents or []:
        enc_id = _get(doc, "encounter_id")
        add(
            build_document_reference(
                doc, patient_id, str(enc_id) if enc_id else None
            )
        )

    for item in clinical_items or []:
        resource = build_clinical_item(item, patient_id)
        if resource is not None:
            add(resource)

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(entries),
        "entry": entries,
    }


def resource_type_counts(bundle: dict[str, Any]) -> dict[str, int]:
    """Utility: count resourceTypes present in a bundle (for tests/reporting)."""
    counts: dict[str, int] = {}
    for entry in bundle.get("entry", []):
        rt = entry.get("resource", {}).get("resourceType")
        if rt:
            counts[rt] = counts.get(rt, 0) + 1
    return counts


# Re-export for callers that only import the builder module.
__all__ = [
    "build_patient_bundle",
    "build_patient",
    "build_encounter",
    "build_document_reference",
    "build_clinical_item",
    "resource_type_counts",
    "fhir_resource_for",
]
