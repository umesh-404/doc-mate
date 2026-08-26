"""Ambient consultation scribe.

Captures the consultation itself — the one part of the visit Doc-mate did not
yet see — and turns it into a **draft** note the doctor edits and verifies.
Verified content becomes part of the record and feeds the next visit's snapshot,
closing the loop.

Safety (PROJECT.md section 4): the scribe proposes, it never concludes. There is
deliberately **no assessment/diagnosis section** — the note is
Subjective / Objective / Plan-as-discussed / Follow-up / Flags, and it only ever
contains content that was actually said. Nothing is written into the patient's
record until a human presses verify.

Public surface:

* ``structure_note(transcript, language=..., use_llm=...)`` -> note payload
  ``{"sections": [...], "proposed_items": [...], "meta": {...}}`` (pure).
* ``propose_items(transcript, confidence=...)`` -> verbatim clinical candidates.
* ``SECTION_KEYS`` / ``SECTION_TITLES`` — the five allowed section keys.
* pipeline helpers for the router (``create_note``, ``process_note``,
  ``note_payload``, ``verify_note``).
"""

from __future__ import annotations

from app.consult.structure import (
    SECTION_KEYS,
    SECTION_TITLES,
    propose_items,
    structure_note,
)

__all__ = [
    "SECTION_KEYS",
    "SECTION_TITLES",
    "propose_items",
    "structure_note",
]
