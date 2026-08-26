"""Unit tests for the summary quality evaluation harness (app.eval).

All function-level — no DB, no LLM, no network. Verifies the three axes behave
as documented: a perfectly grounded summary is faithful, a fabricated number is
caught and named, an omitted allergy is reported as missed, conciseness stays
bounded, and degenerate inputs never crash.
"""

from __future__ import annotations

import uuid

from app.eval.metrics import (
    EVAL_METHOD,
    OVERALL_WEIGHTS,
    important_facts,
    score_completeness,
    score_conciseness,
    score_faithfulness,
    score_summary,
)

DOC = str(uuid.uuid4())
CITE = [{"document_id": DOC, "label": "Lab • 01 Jun"}]


def _fact(kind, label, value=None, unit=None, verified=True, date="2026-06-01"):
    return {
        "kind": kind,
        "label": label,
        "value": value,
        "unit": unit,
        "date": date,
        "confidence": 0.95,
        "verified": verified,
        "document_id": DOC,
        "citation_label": "Lab • 01 Jun",
    }


def _section(key, title, texts):
    return {
        "key": key,
        "title": title,
        "items": [{"text": t, "citations": list(CITE)} for t in texts],
    }


# ---------------------------------------------------------------------------
# Faithfulness
# ---------------------------------------------------------------------------
def test_perfectly_grounded_summary_is_fully_faithful() -> None:
    context = [
        _fact("observation", "HbA1c", "7.8", "%"),
        _fact("allergy", "Penicillin"),
    ]
    sections = [
        _section("labs", "Recent labs", ["HbA1c: 7.8 %"]),
        _section("allergies", "Allergies", ["Penicillin"]),
    ]
    score, details = score_faithfulness(sections, context)
    assert score == 1.0
    assert details["unsupported_count"] == 0
    assert details["graded_items"] == 2


def test_fabricated_number_lowers_faithfulness_and_names_the_item() -> None:
    context = [_fact("observation", "HbA1c", "7.8", "%")]
    sections = [
        _section("labs", "Recent labs", ["HbA1c: 7.8 %", "HbA1c: 12.4 % last month"])
    ]
    score, details = score_faithfulness(sections, context)
    assert score < 1.0
    assert details["unsupported_count"] == 1
    offending = details["unsupported"][0]
    assert "12.4" in offending["text"]
    assert offending["reason"]


def test_flags_section_is_not_graded_for_faithfulness() -> None:
    context = [_fact("observation", "HbA1c", "7.8", "%")]
    sections = [
        {
            "key": "flags",
            "title": "Flags",
            "items": [{"text": "One upload could not be read.", "citations": []}],
        }
    ]
    score, details = score_faithfulness(sections, context)
    assert score == 1.0
    assert details["graded_items"] == 0


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------
def test_omitted_allergy_is_reported_as_missed() -> None:
    context = [
        _fact("allergy", "Penicillin"),
        _fact("observation", "HbA1c", "7.8", "%"),
    ]
    sections = [_section("labs", "Recent labs", ["HbA1c: 7.8 %"])]
    score, details = score_completeness(sections, context)
    assert score < 1.0
    labels = [m["label"] for m in details["missed"]]
    assert "Penicillin" in labels
    assert details["missed_count"] == 1
    assert details["covered_count"] == 1


def test_all_important_facts_present_scores_full_completeness() -> None:
    context = [
        _fact("allergy", "Penicillin"),
        _fact("condition", "Type 2 diabetes mellitus"),
        _fact("medication", "Metformin", "500mg 1-0-1"),
        _fact("observation", "HbA1c", "7.8", "%"),
    ]
    sections = [
        _section("allergies", "Allergies", ["Penicillin — confirm before prescribing"]),
        _section("problems", "Problems", ["Type 2 diabetes mellitus"]),
        _section("medications", "Medications", ["Metformin 500mg 1-0-1"]),
        _section("labs", "Recent labs", ["HbA1c: 7.8 %"]),
    ]
    score, details = score_completeness(sections, context)
    assert score == 1.0
    assert details["missed"] == []


def test_unverified_medication_is_not_required() -> None:
    context = [_fact("medication", "Amoxicillin", "500mg", verified=False)]
    facts = important_facts(context)
    assert facts == []
    score, details = score_completeness([], context)
    assert score == 1.0
    assert details["important_fact_count"] == 0


def test_older_lab_value_not_required_but_abnormal_one_is() -> None:
    # Newest first, as gather_context returns them.
    context = [
        _fact("observation", "HbA1c", "7.8", "%", date="2026-06-01"),
        _fact("observation", "HbA1c", "9.9", "%", date="2025-01-01"),
        _fact("observation", "Hemoglobin", "13.5", "g/dL", date="2026-06-01"),
        _fact("observation", "Hemoglobin", "13.2", "g/dL", date="2025-01-01"),
    ]
    reasons = {(f["label"], f["value"]): f["_reason"] for f in important_facts(context)}
    # Most recent of each label is required.
    assert ("HbA1c", "7.8") in reasons
    assert ("Hemoglobin", "13.5") in reasons
    # The old abnormal HbA1c (9.9 > 6.5) is still required; the old normal
    # hemoglobin is not.
    assert ("HbA1c", "9.9") in reasons
    assert ("Hemoglobin", "13.2") not in reasons


# ---------------------------------------------------------------------------
# Conciseness
# ---------------------------------------------------------------------------
def test_conciseness_is_bounded_between_zero_and_one() -> None:
    dense = [_section("labs", "Labs", ["HbA1c 7.8"])]
    score, details = score_conciseness(dense, covered_fact_count=5)
    assert 0.0 <= score <= 1.0
    assert score == 1.0  # very dense -> capped at 1.0
    assert details["word_count"] > 0

    padded = [
        _section(
            "labs",
            "Labs",
            ["the patient " * 60 + "HbA1c 7.8"],
        )
    ]
    low, _ = score_conciseness(padded, covered_fact_count=1)
    assert 0.0 <= low < 1.0


def test_conciseness_does_not_reward_dropping_facts() -> None:
    """Halving the words while halving the facts conveyed must not improve."""
    full = [_section("labs", "Labs", ["HbA1c is 7.8 percent today", "LDL is 150"])]
    trimmed = [_section("labs", "Labs", ["HbA1c is 7.8 percent today"])]
    full_score, _ = score_conciseness(full, covered_fact_count=2)
    trimmed_score, _ = score_conciseness(trimmed, covered_fact_count=1)
    assert trimmed_score <= full_score


def test_conciseness_empty_summary_conveying_nothing_scores_zero() -> None:
    score, details = score_conciseness([], covered_fact_count=3)
    assert score == 0.0
    assert details["word_count"] == 0


# ---------------------------------------------------------------------------
# Combined scoring
# ---------------------------------------------------------------------------
def test_score_summary_shape_and_weights() -> None:
    context = [_fact("observation", "HbA1c", "7.8", "%")]
    sections = [_section("labs", "Recent labs", ["HbA1c: 7.8 %"])]
    result = score_summary(sections, context)

    for axis in ("faithfulness", "completeness", "conciseness", "overall"):
        assert 0.0 <= result[axis] <= 1.0
    assert result["method"] == EVAL_METHOD
    assert set(result["details"]) == {
        "faithfulness",
        "completeness",
        "conciseness",
        "weights",
    }
    expected = (
        OVERALL_WEIGHTS["faithfulness"] * result["faithfulness"]
        + OVERALL_WEIGHTS["completeness"] * result["completeness"]
        + OVERALL_WEIGHTS["conciseness"] * result["conciseness"]
    )
    assert abs(result["overall"] - expected) < 1e-6
    # Faithfulness must carry the most weight.
    assert OVERALL_WEIGHTS["faithfulness"] > OVERALL_WEIGHTS["completeness"]
    assert abs(sum(OVERALL_WEIGHTS.values()) - 1.0) < 1e-9


def test_hallucinated_summary_scores_below_grounded_one() -> None:
    context = [_fact("observation", "HbA1c", "7.8", "%")]
    good = score_summary([_section("labs", "Labs", ["HbA1c: 7.8 %"])], context)
    bad = score_summary(
        [_section("labs", "Labs", ["HbA1c: 7.8 %", "Troponin: 15.2 ng/mL"])], context
    )
    assert bad["faithfulness"] < good["faithfulness"]
    assert bad["overall"] < good["overall"]


# ---------------------------------------------------------------------------
# Degenerate inputs
# ---------------------------------------------------------------------------
def test_empty_inputs_do_not_crash() -> None:
    result = score_summary([], [])
    assert result["faithfulness"] == 1.0
    assert result["completeness"] == 1.0
    assert result["conciseness"] == 1.0
    assert result["overall"] == 1.0


def test_none_inputs_do_not_crash() -> None:
    result = score_summary(None, None)
    assert result["overall"] == 1.0


def test_summary_with_no_context_is_unfaithful_not_crashing() -> None:
    sections = [_section("labs", "Labs", ["HbA1c: 7.8 %"])]
    result = score_summary(sections, [])
    assert result["faithfulness"] == 0.0
    assert result["completeness"] == 1.0  # nothing was required
    assert 0.0 <= result["overall"] <= 1.0


def test_sections_with_empty_items_and_blank_text() -> None:
    sections = [
        {"key": "labs", "title": "Labs", "items": []},
        {"key": "problems", "title": "Problems", "items": [{"text": "", "citations": []}]},
    ]
    result = score_summary(sections, [_fact("allergy", "Penicillin")])
    assert 0.0 <= result["overall"] <= 1.0
    assert result["details"]["completeness"]["missed_count"] == 1
