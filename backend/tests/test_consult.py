"""Unit tests for the ambient consultation scribe.

Pure-function tests only: no Postgres, no object storage, no provider key. They
pin down the safety contract (PROJECT.md section 4) as much as the shape —
no diagnosis section, no fabrication, uncertainty always surfaced.
"""

from __future__ import annotations

from app.consult.structure import (
    FORBIDDEN_SECTION_KEYS,
    SECTION_KEYS,
    propose_items,
    structure_note,
)

TRANSCRIPT = (
    "Patient reports fever and cough for the past three days. "
    "She says the cough is worse at night. "
    "On examination, BP is 130/85 and pulse 88. "
    "Temperature 38.2 C. "
    "Known type 2 diabetes; HbA1c 7.8 %. "
    "She is allergic to penicillin. "
    "Continue Metformin 500mg twice a day. "
    "I think there may be a dust allergy but I'm not sure. "
    "Review in two weeks."
)


def _sections(payload: dict) -> dict[str, list[dict]]:
    return {s["key"]: s["items"] for s in payload["sections"]}


def _all_text(payload: dict) -> str:
    return " ".join(
        item["text"] for section in payload["sections"] for item in section["items"]
    ).lower()


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------
def test_note_has_exactly_the_five_allowed_sections() -> None:
    payload = structure_note(TRANSCRIPT)
    keys = [section["key"] for section in payload["sections"]]
    assert keys == list(SECTION_KEYS)
    assert keys == ["subjective", "objective", "plan", "follow_up", "flags"]
    for section in payload["sections"]:
        assert section["title"]
        assert isinstance(section["items"], list)
        for item in section["items"]:
            assert set(item) == {"text", "needs_verification"}
            assert isinstance(item["needs_verification"], bool)


def test_no_section_states_a_diagnosis() -> None:
    """The scribe proposes; it never concludes. No assessment key may exist."""
    payload = structure_note(TRANSCRIPT)
    keys = {section["key"] for section in payload["sections"]}
    assert keys.isdisjoint(FORBIDDEN_SECTION_KEYS)
    assert "assessment" not in keys
    assert "diagnosis" not in keys
    titles = " ".join(section["title"] for section in payload["sections"]).lower()
    for banned in ("assessment", "diagnosis", "impression"):
        assert banned not in titles


def test_sentences_are_routed_and_never_rewritten() -> None:
    sections = _sections(structure_note(TRANSCRIPT))
    subjective = [i["text"] for i in sections["subjective"]]
    objective = [i["text"] for i in sections["objective"]]
    plan = [i["text"] for i in sections["plan"]]
    follow_up = [i["text"] for i in sections["follow_up"]]

    assert "Patient reports fever and cough for the past three days." in subjective
    assert "On examination, BP is 130/85 and pulse 88." in objective
    assert "Continue Metformin 500mg twice a day." in plan
    assert "Review in two weeks." in follow_up


def test_every_note_line_comes_from_the_transcript() -> None:
    """Nothing outside `flags` may be invented — every line must be spoken."""
    payload = structure_note(TRANSCRIPT)
    for section in payload["sections"]:
        if section["key"] == "flags":
            continue
        for item in section["items"]:
            assert item["text"] in TRANSCRIPT


def test_uncertain_content_is_flagged_needs_verification() -> None:
    payload = structure_note(TRANSCRIPT)
    sections = _sections(payload)
    hedged = [
        item
        for items in sections.values()
        for item in items
        if "not sure" in item["text"].lower()
    ]
    assert hedged, "the hedged sentence should appear in the note"
    assert all(item["needs_verification"] for item in hedged)

    flags = sections["flags"]
    assert any("⚠ needs verification" in item["text"] for item in flags)
    assert all(item["needs_verification"] for item in flags)
    # And the standing reminder that this is a draft, not a conclusion.
    assert any("draft only" in item["text"].lower() for item in flags)


def test_confident_sentences_are_not_over_flagged() -> None:
    sections = _sections(structure_note(TRANSCRIPT))
    plain = [
        item
        for item in sections["objective"]
        if item["text"] == "Temperature 38.2 C."
    ]
    assert plain and plain[0]["needs_verification"] is False


def test_stub_transcript_is_declared_in_flags() -> None:
    payload = structure_note(TRANSCRIPT, stub_transcript=True)
    flags = _sections(payload)["flags"]
    assert any("offline demo fallback" in item["text"] for item in flags)


def test_empty_transcript_yields_empty_note_not_a_confident_one() -> None:
    payload = structure_note("")
    sections = _sections(payload)
    assert sections["subjective"] == []
    assert sections["objective"] == []
    assert sections["plan"] == []
    assert payload["proposed_items"] == []
    assert any("No consultation content" in i["text"] for i in sections["flags"])


def test_structure_is_deterministic() -> None:
    assert structure_note(TRANSCRIPT) == structure_note(TRANSCRIPT)


# ---------------------------------------------------------------------------
# Proposed clinical items
# ---------------------------------------------------------------------------
def _by_kind(items: list[dict], kind: str) -> list[dict]:
    return [i for i in items if i["kind"] == kind]


def test_proposed_items_preserve_exact_dose_strings() -> None:
    items = propose_items(TRANSCRIPT)
    meds = _by_kind(items, "medication")
    labels = [m["label"] for m in meds]
    assert "Metformin 500mg" in labels
    # The verbatim span must survive — no re-spacing, no unit normalization.
    for label in labels:
        assert label in TRANSCRIPT
    metformin = next(m for m in meds if m["label"] == "Metformin 500mg")
    assert metformin["value"] == "twice a day"


def test_dose_spacing_variants_stay_byte_for_byte() -> None:
    for spoken in ("Metformin 500mg", "Metformin 500 mg", "Amlodipine 5mg"):
        items = propose_items(f"Continue {spoken} daily.")
        assert [i["label"] for i in _by_kind(items, "medication")] == [spoken]


def test_vitals_and_labs_are_extracted_with_spoken_values() -> None:
    items = propose_items(TRANSCRIPT)
    observations = {i["label"]: i for i in _by_kind(items, "observation")}
    assert observations["Blood pressure"]["value"] == "130/85"
    assert observations["Pulse"]["value"] == "88"
    assert observations["Temperature"]["value"] == "38.2"
    assert "HbA1c" in observations
    assert observations["HbA1c"]["value"] == "7.8"


def test_conditions_and_allergies_come_from_the_words_spoken() -> None:
    items = propose_items(TRANSCRIPT)
    conditions = [i["label"].lower() for i in _by_kind(items, "condition")]
    assert "type 2 diabetes" in conditions
    allergies = [i["label"].lower() for i in _by_kind(items, "allergy")]
    assert "penicillin" in allergies


def test_nothing_is_fabricated_when_absent() -> None:
    """A transcript with no drug, vital, or condition proposes nothing."""
    bland = (
        "Patient came in for a general check. "
        "She feels well and has no new complaints today."
    )
    assert propose_items(bland) == []
    payload = structure_note(bland)
    assert payload["proposed_items"] == []


def test_lab_values_are_never_mistaken_for_medications() -> None:
    items = propose_items("Hemoglobin 11.2 g/dL and creatinine 1.1 mg/dL.")
    assert _by_kind(items, "medication") == []
    labels = {i["label"].lower() for i in _by_kind(items, "observation")}
    assert "hemoglobin" in labels
    assert "creatinine" in labels


def test_units_are_only_reported_when_spoken() -> None:
    spoken = propose_items("HbA1c 7.8 %")
    assert spoken[0]["unit"] == "%"
    unspoken = propose_items("HbA1c 7.8")
    assert unspoken[0]["unit"] is None


def test_every_proposed_item_needs_doctor_verification() -> None:
    items = propose_items(TRANSCRIPT)
    assert items
    assert all(item["needs_verification"] is True for item in items)
    assert all(
        set(item) == {"kind", "label", "value", "unit", "confidence", "needs_verification"}
        for item in items
    )


def test_proposed_item_order_is_stable() -> None:
    """`item_indexes` on verify indexes into this list, so order must not drift."""
    first = [i["label"] for i in propose_items(TRANSCRIPT)]
    second = [i["label"] for i in propose_items(TRANSCRIPT)]
    assert first == second


def test_duplicate_mentions_are_collapsed() -> None:
    text = "Continue Metformin 500mg. Again, Metformin 500mg after food."
    assert len(_by_kind(propose_items(text), "medication")) == 1
