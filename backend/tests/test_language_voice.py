"""Function-level tests for the multilingual + voice layers (no DB, offline).

Verifies the non-negotiable safety property (PROJECT.md section 4): stub
translation NEVER alters a clinical value (doses, lab numbers), and the offline
voice path always returns a usable stub transcription.
"""

from __future__ import annotations

from app.language import (
    is_stub_mode,
    plain_language,
    translate_sections,
    translate_text,
)
from app.language import glossary
from app.voice import transcribe


def _sample_sections() -> list[dict]:
    return [
        {
            "key": "medications",
            "title": "Current medications",
            "items": [
                {
                    "text": "Metformin 500mg — 1-0-1",
                    "verified": True,
                    "citations": [{"document_id": "doc-1", "label": "Rx"}],
                }
            ],
        },
        {
            "key": "labs",
            "title": "Recent labs & trends",
            "items": [
                {
                    "text": "HbA1c: 7.8 %",
                    "trend": "up",
                    "citations": [{"document_id": "doc-2", "label": "Lab"}],
                }
            ],
        },
        {"key": "flags", "title": "Flags & things to verify", "items": []},
    ]


def test_stub_mode_is_default() -> None:
    # With no LLM_PROVIDER / key configured, the offline path is in effect.
    assert is_stub_mode() is True


def test_translation_preserves_dose_hindi() -> None:
    out = translate_text("Metformin 500mg — 1-0-1", "hi")
    assert "500mg" in out
    assert "1-0-1" in out


def test_translation_preserves_lab_value_tamil() -> None:
    out = translate_text("HbA1c: 7.8 %", "ta")
    assert "7.8" in out


def test_section_titles_translated_hi_and_ta() -> None:
    hi = translate_sections(_sample_sections(), "hi")
    ta = translate_sections(_sample_sections(), "ta")

    hi_meds = next(s for s in hi if s["key"] == "medications")
    ta_meds = next(s for s in ta if s["key"] == "medications")

    # Title differs from English and matches the bundled glossary.
    assert hi_meds["title"] == glossary.section_titles("hi")["Current medications"]
    assert ta_meds["title"] == glossary.section_titles("ta")["Current medications"]
    assert hi_meds["title"] != "Current medications"

    # Structure + citations + numbers are carried through unchanged.
    item = hi_meds["items"][0]
    assert item["citations"] == [{"document_id": "doc-1", "label": "Rx"}]
    assert "500mg" in item["text"]


def test_english_is_passthrough() -> None:
    text = "Metformin 500mg"
    assert translate_text(text, "en") == text


def test_plain_language_returns_text() -> None:
    text_en = plain_language(_sample_sections(), "en")
    assert isinstance(text_en, str) and len(text_en) > 0
    assert "500mg" in text_en  # clinical value survives simplification

    text_hi = plain_language(_sample_sections(), "hi")
    assert isinstance(text_hi, str) and len(text_hi) > 0
    assert "7.8" in text_hi


def test_voice_transcribe_stub() -> None:
    result = transcribe(b"\x00\x01fake-audio-bytes", filename="note.wav")
    assert result["stub"] is True
    assert isinstance(result["text"], str) and result["text"]
    assert "lang" in result and "confidence" in result


def test_voice_transcribe_is_deterministic() -> None:
    a = transcribe(b"same-bytes", filename="a.wav")
    b = transcribe(b"same-bytes", filename="a.wav")
    assert a["text"] == b["text"]
