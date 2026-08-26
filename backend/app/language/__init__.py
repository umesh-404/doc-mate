"""Multilingual layer: translate + simplify the doctor's patient snapshot.

Public surface (all offline-safe; real mode routed through ``app.llm``):

* ``translate_sections(sections, lang)`` — translate section titles + item text
  into ``lang`` (en|hi|ta), preserving numbers/doses/drug names/citations.
* ``translate_text(text, lang)`` — translate one string with the same guarantee.
* ``plain_language(sections, lang)`` — patient-friendly plain narrative.
* ``is_stub_mode()`` / ``stub_note(lang)`` — reflect and label the stub path.

SAFETY (PROJECT.md section 4): clinical values are never altered by translation.
"""

from __future__ import annotations

from app.language.glossary import SUPPORTED_LANGS
from app.language.simplify import plain_language
from app.language.translate import (
    is_stub_mode,
    stub_note,
    translate_sections,
    translate_text,
)

__all__ = [
    "SUPPORTED_LANGS",
    "translate_sections",
    "translate_text",
    "plain_language",
    "is_stub_mode",
    "stub_note",
]
