"""Offline unit tests for interoperability: FHIR bundle, coding, mock ABHA.

Runs without a database, object store, or provider credentials. FHIR bundles are
built from small in-memory fake rows (plain objects), so the resource shape and
reference wiring are exercised directly.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.coding import coverage, map_condition, search
from app.fhir.abha import mock_identity
from app.fhir.builder import build_patient_bundle, resource_type_counts


# ---------------------------------------------------------------------------
# Fake rows (attribute access, like ORM instances) — no DB needed.
# ---------------------------------------------------------------------------
def _fake_patient() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        abha_id="12345678901234",
        full_name="Test Patient",
        sex="F",
        gender="female",
        age=54,
        date_of_birth=None,
        phone="+91-9000000000",
        preferred_language="hi",
        created_at=None,
    )


def _fake_item(kind: str, label: str, patient_id, doc_id, **kw) -> SimpleNamespace:
    base = dict(
        id=uuid.uuid4(),
        patient_id=patient_id,
        source_document_id=doc_id,
        kind=kind,
        label=label,
        value=None,
        unit=None,
        effective_date=None,
        verified=True,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _build_sample_bundle():
    patient = _fake_patient()
    pid = patient.id
    doc = SimpleNamespace(
        id=uuid.uuid4(),
        patient_id=pid,
        encounter_id=None,
        doc_type="lab_report",
        status="verified",
        filename="labs.pdf",
        content_type="application/pdf",
        created_at=None,
    )
    enc = SimpleNamespace(
        id=uuid.uuid4(),
        patient_id=pid,
        reason="Routine follow-up",
        status="in_progress",
        occurred_at=None,
    )
    items = [
        _fake_item("condition", "Type 2 diabetes mellitus", pid, doc.id),
        _fake_item("condition", "Essential hypertension", pid, doc.id),
        _fake_item("observation", "HbA1c", pid, doc.id, value="8.1", unit="%"),
        _fake_item("medication", "Metformin 500mg", pid, doc.id, value="1-0-1"),
        _fake_item("allergy", "Penicillin", pid, doc.id, verified=False),
        _fake_item("procedure", "Appendectomy", pid, doc.id),
    ]
    bundle = build_patient_bundle(
        patient, encounters=[enc], documents=[doc], clinical_items=items
    )
    return patient, doc, enc, items, bundle


# ---------------------------------------------------------------------------
# FHIR bundle tests
# ---------------------------------------------------------------------------
def test_bundle_is_collection_and_has_expected_resource_types() -> None:
    _, _, _, _, bundle = _build_sample_bundle()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"

    counts = resource_type_counts(bundle)
    for rt in (
        "Patient",
        "Encounter",
        "DocumentReference",
        "Condition",
        "Observation",
        "MedicationRequest",
        "AllergyIntolerance",
        "Procedure",
    ):
        assert counts.get(rt, 0) >= 1, f"missing {rt}"
    assert bundle["total"] == len(bundle["entry"])


def test_references_resolve_within_bundle() -> None:
    patient, _, _, _, bundle = _build_sample_bundle()
    pid = str(patient.id)

    resources = [e["resource"] for e in bundle["entry"]]
    ids = {(r["resourceType"], r["id"]) for r in resources}
    assert ("Patient", pid) in ids

    def ref_ok(ref: str) -> bool:
        rtype, _, rid = ref.partition("/")
        return (rtype, rid) in ids

    for r in resources:
        subj = r.get("subject") or r.get("patient")
        if subj and "reference" in subj:
            assert ref_ok(subj["reference"]), subj["reference"]


def test_condition_carries_icd11_code() -> None:
    _, _, _, _, bundle = _build_sample_bundle()
    conditions = [
        e["resource"]
        for e in bundle["entry"]
        if e["resource"]["resourceType"] == "Condition"
    ]
    dm = next(
        c for c in conditions if "diabetes" in c["code"]["text"].lower()
    )
    codings = dm["code"].get("coding", [])
    assert any(cd["code"] == "5A11" for cd in codings)
    assert any("id.who.int/icd" in cd["system"] for cd in codings)


def test_patient_resource_maps_abha_and_language() -> None:
    patient, _, _, _, bundle = _build_sample_bundle()
    p = next(
        e["resource"]
        for e in bundle["entry"]
        if e["resource"]["resourceType"] == "Patient"
    )
    assert p["gender"] == "female"
    assert any(i.get("value") == patient.abha_id for i in p["identifier"])
    assert any(
        "healthid" in i.get("system", "") for i in p["identifier"]
    )
    langs = p["communication"][0]["language"]["coding"][0]["code"]
    assert langs == "hi"


def test_observation_numeric_value_quantity() -> None:
    _, _, _, _, bundle = _build_sample_bundle()
    obs = next(
        e["resource"]
        for e in bundle["entry"]
        if e["resource"]["resourceType"] == "Observation"
    )
    assert obs["valueQuantity"]["value"] == 8.1
    assert obs["valueQuantity"]["unit"] == "%"


# ---------------------------------------------------------------------------
# Coding tests
# ---------------------------------------------------------------------------
def test_map_condition_type2_diabetes_returns_5a11() -> None:
    codes = map_condition("Type 2 diabetes mellitus")
    icd = [c for c in codes if c.system == "ICD-11"]
    assert icd, "expected an ICD-11 code"
    assert icd[0].code == "5A11"


def test_map_condition_substring_and_case_insensitive() -> None:
    codes = map_condition("HYPERTENSION")
    assert any(c.code == "BA00" for c in codes if c.system == "ICD-11")


def test_map_condition_unknown_returns_empty_no_fabrication() -> None:
    assert map_condition("zzz nonexistent finding qwerty") == []
    assert map_condition("") == []


def test_search_by_system_filter() -> None:
    icd = search("diabetes", system="icd11")
    assert icd and all(c.system == "ICD-11" for c in icd)
    nam = search("diabetes", system="namaste")
    assert nam and all(c.system == "NAMASTE" for c in nam)


def test_coverage_counts_reasonable() -> None:
    cov = coverage()
    assert cov.get("ICD-11", 0) >= 40
    assert cov.get("NAMASTE", 0) >= 5


# ---------------------------------------------------------------------------
# Mock ABHA tests
# ---------------------------------------------------------------------------
def test_mock_abha_shape_and_determinism() -> None:
    ident = mock_identity("98765432109876")
    assert set(ident.keys()) == {
        "abha_id",
        "name",
        "gender",
        "year_of_birth",
        "verified",
        "source",
    }
    assert ident["source"] == "mock"
    assert ident["verified"] is True
    assert ident["gender"] in {"male", "female", "other"}
    assert isinstance(ident["year_of_birth"], int)
    # Deterministic: same id -> same identity.
    assert mock_identity("98765432109876") == ident
    # Different id -> (very likely) different identity.
    assert mock_identity("11112222333344") != ident
