"""Unit tests for the clinical-safety layer.

All function-level — no DB, no LLM, no network. Exercises the grounding scorer,
the offline interaction / allergy checker, and alert assembly (PROJECT.md
section 4).
"""

from __future__ import annotations

import uuid

from app.safety.alerts import build_alerts
from app.safety.grounding import GROUNDING_METHOD, check_grounding
from app.safety.interactions import (
    check_allergy_conflicts,
    check_interactions,
    normalize_drug,
)

DOC = str(uuid.uuid4())


def _fact(kind, label, value=None, unit=None):
    return {
        "kind": kind,
        "label": label,
        "value": value,
        "unit": unit,
        "date": "2026-06-01",
        "confidence": 0.9,
        "verified": True,
        "document_id": DOC,
        "citation_label": "Lab • 01 Jun",
    }


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------
def test_grounded_item_scores_full() -> None:
    context = [_fact("observation", "HbA1c", "7.8", "%")]
    sections = [
        {
            "key": "labs",
            "title": "Recent labs & trends",
            "items": [
                {
                    "text": "HbA1c: 7.8 %",
                    "citations": [{"document_id": DOC, "label": "Lab • 01 Jun"}],
                }
            ],
        }
    ]
    out, grounding = check_grounding(sections, context)
    assert grounding["score"] == 1.0
    assert grounding["unsupported_count"] == 0
    assert grounding["method"] == GROUNDING_METHOD
    assert out[0]["items"][0]["grounded"] is True
    assert out[0]["items"][0]["grounding_note"] is None


def test_fabricated_item_is_flagged() -> None:
    # Source says HbA1c 7.8; the line invents a different value + entity.
    context = [_fact("observation", "HbA1c", "7.8", "%")]
    sections = [
        {
            "key": "labs",
            "title": "Recent labs & trends",
            "items": [
                {
                    "text": "Troponin: 15.2 ng/mL, markedly elevated",
                    "citations": [{"document_id": DOC, "label": "Lab • 01 Jun"}],
                }
            ],
        }
    ]
    out, grounding = check_grounding(sections, context)
    item = out[0]["items"][0]
    assert item["grounded"] is False
    assert item["grounding_note"]
    assert grounding["score"] == 0.0
    assert grounding["unsupported_count"] == 1


def test_flags_section_not_graded() -> None:
    context = [_fact("observation", "HbA1c", "7.8", "%")]
    sections = [
        {
            "key": "flags",
            "title": "Flags",
            "items": [{"text": "Anything at all here", "citations": []}],
        }
    ]
    out, grounding = check_grounding(sections, context)
    # No non-flags items -> score defaults to 1.0, item left untouched.
    assert grounding["score"] == 1.0
    assert "grounded" not in out[0]["items"][0]


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------
def test_normalize_strips_dose_and_frequency() -> None:
    assert normalize_drug("Amoxicillin 500mg 1-0-1") == "amoxicillin"
    assert normalize_drug("Warfarin 5mg OD") == "warfarin"


def test_warfarin_aspirin_interaction() -> None:
    results = check_interactions(["Warfarin 5mg", "Aspirin 75mg"])
    assert len(results) == 1
    r = results[0]
    assert r["severity"] in {"major", "contraindicated"}
    assert {r["drug_a"], r["drug_b"]} == {"Warfarin 5mg", "Aspirin 75mg"}
    assert r["source"]


def test_no_interaction_for_unrelated_meds() -> None:
    assert check_interactions(["Paracetamol 500mg", "Cetirizine 10mg"]) == []


def test_class_based_interaction() -> None:
    # ACE inhibitor + potassium-sparing diuretic -> hyperkalaemia (major).
    results = check_interactions(["Lisinopril 10mg", "Spironolactone 25mg"])
    assert any(r["severity"] == "major" for r in results)


def test_single_drug_no_self_interaction() -> None:
    assert check_interactions(["Warfarin 5mg"]) == []


# ---------------------------------------------------------------------------
# Allergy conflicts
# ---------------------------------------------------------------------------
def test_penicillin_allergy_amoxicillin_conflict() -> None:
    conflicts = check_allergy_conflicts(["Amoxicillin 500mg"], ["Penicillin"])
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["medication"] == "Amoxicillin 500mg"
    assert c["allergen"] == "Penicillin"
    assert c["note"] and c["source"]


def test_no_allergy_conflict_when_unrelated() -> None:
    assert check_allergy_conflicts(["Metformin 500mg"], ["Penicillin"]) == []


# ---------------------------------------------------------------------------
# Alert assembly
# ---------------------------------------------------------------------------
def test_build_alerts_covers_all_kinds() -> None:
    context = [
        _fact("allergy", "Penicillin"),
        _fact("medication", "Amoxicillin 500mg", "1-0-1"),
        _fact("medication", "Warfarin 5mg", "0-0-1"),
        _fact("medication", "Aspirin 75mg", "1-0-0"),
        _fact("observation", "HbA1c", "7.8", "%"),
    ]
    alerts = build_alerts(context)
    kinds = {a["kind"] for a in alerts}
    assert "allergy" in kinds  # recorded penicillin allergy + amox conflict
    assert "interaction" in kinds  # warfarin + aspirin
    assert "abnormal_lab" in kinds  # HbA1c 7.8 > 6.5

    # Critical alerts sort first.
    assert alerts[0]["level"] == "critical"
    # Every alert has the required shape.
    for a in alerts:
        assert a["level"] in {"critical", "warning", "info"}
        assert a["text"]
        assert "citations" in a


def test_build_alerts_missing_data() -> None:
    alerts = build_alerts([])
    assert any(a["kind"] == "missing_data" for a in alerts)


def test_missing_allergy_info_flagged() -> None:
    context = [_fact("medication", "Metformin 500mg", "1-0-1")]
    alerts = build_alerts(context)
    assert any(
        a["kind"] == "missing_data" and "allergy" in a["text"].lower()
        for a in alerts
    )
