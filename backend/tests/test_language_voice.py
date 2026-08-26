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


def test_translation_preserves_dose_telugu() -> None:
    out = translate_text("Metformin 500mg — 1-0-1", "te")
    assert "500mg" in out
    assert "1-0-1" in out
    # Drug names are never translated away.
    assert "Metformin" in out


def test_translation_preserves_lab_value_telugu() -> None:
    out = translate_text("HbA1c: 7.8 %", "te")
    assert "7.8" in out
    assert "HbA1c" in out


def test_section_titles_translated_telugu() -> None:
    te = translate_sections(_sample_sections(), "te")

    te_meds = next(s for s in te if s["key"] == "medications")
    assert te_meds["title"] == glossary.section_titles("te")["Current medications"]
    assert te_meds["title"] != "Current medications"
    # Telugu script (U+0C00–U+0C7F) actually came back.
    assert any("ఀ" <= ch <= "౿" for ch in te_meds["title"])

    item = te_meds["items"][0]
    assert item["citations"] == [{"document_id": "doc-1", "label": "Rx"}]
    assert "500mg" in item["text"]
    assert "1-0-1" in item["text"]

    te_labs = next(s for s in te if s["key"] == "labs")
    assert te_labs["title"] == glossary.section_titles("te")["Recent labs & trends"]
    assert te_labs["items"][0]["trend"] == "up"
    assert "7.8" in te_labs["items"][0]["text"]


def test_telugu_is_first_class_language() -> None:
    assert "te" in glossary.SUPPORTED_LANGS

    # The Telugu pack mirrors the Hindi/Tamil packs key-for-key: no missing
    # section title, phrase, plain label, lead or stub note.
    def flat_keys(lang: str) -> set[str]:
        out: set[str] = set()

        def walk(obj: dict, prefix: str = "") -> None:
            for key, value in obj.items():
                out.add(prefix + key)
                if isinstance(value, dict):
                    walk(value, f"{prefix}{key}.")

        walk(glossary.load_pack(lang))
        return out

    assert flat_keys("te") == flat_keys("hi") == flat_keys("ta")

    # Every Telugu value is non-empty and in Telugu script (the English source
    # keys stay English — they are the lookup side of the glossary).
    pack = glossary.load_pack("te")
    assert pack["language"] == "te"
    for value in list(glossary.section_titles("te").values()) + list(
        glossary.plain_labels("te").values()
    ) + [glossary.plain_lead("te"), glossary.stub_note("te")]:
        assert value.strip()
        assert any("ఀ" <= ch <= "౿" for ch in value)


def test_plain_language_telugu() -> None:
    text_te = plain_language(_sample_sections(), "te")
    assert isinstance(text_te, str) and text_te.strip()
    assert any("ఀ" <= ch <= "౿" for ch in text_te)
    # Clinical values survive simplification byte-identically.
    assert "500mg" in text_te
    assert "1-0-1" in text_te
    assert "7.8" in text_te
    assert text_te.startswith(glossary.plain_lead("te"))


def test_telugu_translation_differs_from_hindi_and_tamil() -> None:
    sections = _sample_sections()
    titles = {
        lang: next(
            s for s in translate_sections(sections, lang) if s["key"] == "medications"
        )["title"]
        for lang in ("en", "hi", "ta", "te")
    }
    assert len(set(titles.values())) == 4


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


def test_voice_transcribe_accepts_telugu_hint() -> None:
    # The voice layer has no language whitelist: a requested language code is
    # echoed back untouched, so Telugu intake works like Hindi/Tamil.
    result = transcribe(b"\x00\x01fake-audio-bytes", filename="note.wav", lang="te")
    assert result["lang"] == "te"
    assert result["stub"] is True


def test_voice_transcribe_is_deterministic() -> None:
    a = transcribe(b"same-bytes", filename="a.wav")
    b = transcribe(b"same-bytes", filename="a.wav")
    assert a["text"] == b["text"]
