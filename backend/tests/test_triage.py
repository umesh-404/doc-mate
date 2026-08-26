"""Unit tests for the OPD triage scorer.

Pure functions only — no DB, no LLM, no network. Context facts are built in the
exact shape :func:`app.rag.retrieval.gather_context` returns.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.triage.scoring import (
    THRESHOLD_EMERGENCY,
    THRESHOLD_URGENT,
    TRIAGE_DISCLAIMER,
    score_patient,
)

DOC_A = str(uuid.uuid4())
DOC_B = str(uuid.uuid4())
TODAY = date(2026, 6, 10)


def _fact(kind, label, value=None, unit=None, *, document_id=DOC_A,
          verified=True, fact_date="2026-06-01"):
    return {
        "kind": kind,
        "label": label,
        "value": value,
        "unit": unit,
        "date": fact_date,
        "confidence": 0.9,
        "verified": verified,
        "document_id": document_id,
        "citation_label": "Lab • 01 Jun",
    }


class _P:
    """Minimal stand-in for a Patient row."""

    def __init__(self, age=40):
        self.age = age


# ---------------------------------------------------------------------------
# Empty / degenerate input
# ---------------------------------------------------------------------------
def test_empty_context_is_routine_and_does_not_crash() -> None:
    result = score_patient([], _P(), today=TODAY)
    assert result.level == "routine"
    assert 0 <= result.score <= 100
    assert result.disclaimer == TRIAGE_DISCLAIMER


def test_none_context_and_none_patient() -> None:
    result = score_patient(None, None, today=TODAY)
    assert result.level == "routine"
    assert result.score < THRESHOLD_URGENT


# ---------------------------------------------------------------------------
# Safety flags outrank a routine follow-up
# ---------------------------------------------------------------------------
def test_allergy_conflict_outranks_routine_followup() -> None:
    conflict = score_patient(
        [
            _fact("allergy", "Penicillin allergy"),
            _fact("medication", "Amoxicillin 500mg", document_id=DOC_B),
        ],
        _P(),
        complaint="Sore throat",
        today=TODAY,
    )
    routine = score_patient(
        [_fact("medication", "Metformin 500mg")],
        _P(),
        complaint="Routine follow-up for diabetes review",
        today=TODAY,
    )
    assert conflict.score > routine.score
    assert conflict.level in {"urgent", "emergency"}
    assert routine.level == "routine"


def test_major_interaction_outranks_routine_followup() -> None:
    interaction = score_patient(
        [
            _fact("medication", "Warfarin 5mg"),
            _fact("medication", "Aspirin 75mg", document_id=DOC_B),
        ],
        _P(),
        today=TODAY,
    )
    routine = score_patient(
        [_fact("medication", "Metformin 500mg")],
        _P(),
        complaint="Follow up, repeat prescription",
        today=TODAY,
    )
    assert interaction.score > routine.score
    assert interaction.level in {"urgent", "emergency"}


# ---------------------------------------------------------------------------
# Out-of-range values
# ---------------------------------------------------------------------------
def test_wildly_out_of_range_lab_raises_the_level() -> None:
    mild = score_patient(
        [_fact("observation", "HbA1c", "7.0", "%")], _P(), today=TODAY
    )
    severe = score_patient(
        [_fact("observation", "HbA1c", "14.2", "%")], _P(), today=TODAY
    )
    assert severe.score > mild.score
    assert mild.level == "routine"
    assert severe.level in {"urgent", "emergency"}


def test_severely_low_spo2_is_escalated() -> None:
    result = score_patient(
        [_fact("observation", "SpO2", "84", "%")], _P(), today=TODAY
    )
    assert result.level in {"urgent", "emergency"}


def test_blood_pressure_pair_is_split_and_scored() -> None:
    result = score_patient(
        [_fact("observation", "Blood pressure", "196/124", "mmHg")],
        _P(),
        today=TODAY,
    )
    assert result.level in {"urgent", "emergency"}
    assert any("Systolic BP" in r.text for r in result.reasons)


def test_in_range_observation_adds_nothing() -> None:
    result = score_patient(
        [_fact("observation", "Heart rate", "72", "bpm")], _P(), today=TODAY
    )
    assert result.level == "routine"
    assert not any("Heart rate" in r.text for r in result.reasons)


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------
def test_every_reason_is_cited_when_its_source_fact_had_a_document() -> None:
    result = score_patient(
        [
            _fact("allergy", "Penicillin allergy"),
            _fact("medication", "Amoxicillin 500mg", document_id=DOC_B),
            _fact("observation", "Serum creatinine", "4.1", "mg/dL"),
            _fact("condition", "Type 2 diabetes"),
        ],
        _P(),
        today=TODAY,
    )
    cited = [
        r
        for r in result.reasons
        if "Safety flag" in r.text
        or "Recorded Serum creatinine" in r.text
        or "condition(s) already on record" in r.text
    ]
    assert cited
    for reason in cited:
        assert reason.citations
        for citation in reason.citations:
            assert citation["document_id"] in {DOC_A, DOC_B}
            assert citation["label"]


def test_age_reason_has_no_citation_because_it_has_no_source_document() -> None:
    result = score_patient([], _P(age=88), today=TODAY)
    age_reasons = [r for r in result.reasons if "Elderly patient" in r.text]
    assert age_reasons
    assert age_reasons[0].citations == []


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------
def test_failed_documents_raise_the_score_and_are_named() -> None:
    docs = [
        {"id": DOC_A, "status": "failed", "filename": "scan1.jpg"},
        {"id": DOC_B, "status": "failed", "filename": "scan2.jpg"},
    ]
    with_failures = score_patient([], _P(), documents=docs, today=TODAY)
    without = score_patient([], _P(), documents=[], today=TODAY)
    assert with_failures.score > without.score
    assert any("could not be read" in r.text for r in with_failures.reasons)


def test_unverified_medication_is_flagged() -> None:
    result = score_patient(
        [_fact("medication", "Metformin 500mg", verified=False)],
        _P(),
        today=TODAY,
    )
    assert any("unconfirmed extractions" in r.text for r in result.reasons)


# ---------------------------------------------------------------------------
# Bounds, ordering, and tiering
# ---------------------------------------------------------------------------
def test_score_stays_within_bounds_on_a_worst_case_record() -> None:
    context = [
        _fact("allergy", "Penicillin allergy"),
        _fact("medication", "Amoxicillin 500mg", document_id=DOC_B),
        _fact("medication", "Warfarin 5mg", verified=False),
        _fact("medication", "Aspirin 75mg", verified=False),
        _fact("observation", "SpO2", "80", "%"),
        _fact("observation", "Systolic BP", "210", "mmHg"),
        _fact("observation", "Serum potassium", "7.2", "mmol/L"),
        _fact("observation", "Hemoglobin", "5.1", "g/dL"),
        _fact("condition", "Chronic kidney disease"),
        _fact("condition", "Type 2 diabetes"),
        _fact("condition", "Hypertension"),
    ]
    docs = [{"id": DOC_A, "status": "failed", "filename": "x.jpg"}]
    result = score_patient(
        context,
        _P(age=92),
        documents=docs,
        complaint="Chest pain since morning",
        today=TODAY,
    )
    assert 0 <= result.score <= 100
    assert result.score >= THRESHOLD_EMERGENCY
    assert result.level == "emergency"


def test_reasons_are_ordered_strongest_first() -> None:
    result = score_patient(
        [
            _fact("allergy", "Penicillin allergy"),
            _fact("medication", "Amoxicillin 500mg", document_id=DOC_B),
            _fact("condition", "Hypertension"),
        ],
        _P(age=70),
        today=TODAY,
    )
    weights = [r.weight for r in result.reasons]
    assert weights == sorted(weights, reverse=True)


def test_to_dict_matches_the_api_contract() -> None:
    payload = score_patient(
        [_fact("observation", "HbA1c", "7.2", "%")], _P(), today=TODAY
    ).to_dict()
    assert set(payload) == {
        "level",
        "score",
        "reasons",
        "computed_at",
        "disclaimer",
    }
    for reason in payload["reasons"]:
        assert set(reason) == {"text", "weight", "citations"}


def test_thresholds_are_ordered() -> None:
    assert 0 < THRESHOLD_URGENT < THRESHOLD_EMERGENCY <= 100


def test_no_reason_reads_as_a_diagnosis_or_a_directive() -> None:
    result = score_patient(
        [
            _fact("allergy", "Penicillin allergy"),
            _fact("medication", "Amoxicillin 500mg", document_id=DOC_B),
            _fact("observation", "SpO2", "85", "%"),
        ],
        _P(age=81),
        complaint="Breathless since last night",
        today=TODAY,
    )
    banned = ("treat first", "diagnosis of", "patient has ", "prescribe ")
    for reason in result.reasons:
        lowered = reason.text.lower()
        for phrase in banned:
            assert phrase not in lowered
