"""Consultation-scribe pipeline: capture -> transcribe -> draft -> verify.

Mirrors the ingestion pipeline's shape (PROJECT.md section 6a) but for the
consultation itself::

    audio | typed text
        -> transcript          (app.voice — on-device whisper, stub fallback)
        -> draft note sections  (app.consult.structure, + app.llm in real mode)
        -> proposed clinical items (verbatim, unverified)
        -> [doctor verifies]   -> real ClinicalItem rows -> next visit's snapshot

Status transitions: ``captured`` -> ``transcribing`` -> ``drafted``, or
``failed`` with an ``error_reason``. Processing runs **inline** in the request:
the deterministic path is sub-millisecond and the whisper path is bounded, so
the doctor gets a draft back in the same call rather than polling.

No PHI ever reaches the logs — ids, statuses, and exception *type* names only.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.consult.structure import SECTION_KEYS, SECTION_TITLES, structure_note
from app.core.storage import build_storage_key, put_object
from app.db.models import (
    ClinicalItem,
    ClinicalItemKind,
    ConsultNote,
    ConsultNoteStatus,
    Document,
    DocumentStatus,
    DocumentType,
)

logger = logging.getLogger("docmate.consult")

# Filename of the companion Document that represents the consultation itself.
# ClinicalItem.source_document_id is NOT NULL by design (every fact must be
# citable), so verifying a note first materializes this DocumentReference-shaped
# row; citation chips on the next snapshot then resolve to the consultation.
_CONSULT_DOC_PREFIX = "consultation-note"


def _consult_filename(note_id: uuid.UUID) -> str:
    return f"{_CONSULT_DOC_PREFIX}-{note_id}.txt"


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
def create_note(
    db: Session,
    *,
    patient_id: uuid.UUID,
    author_user_id: uuid.UUID | None,
    language: str = "en",
    encounter_id: uuid.UUID | None = None,
) -> ConsultNote:
    """Create the note row in ``captured`` state and persist it."""
    note = ConsultNote(
        patient_id=patient_id,
        encounter_id=encounter_id,
        author_user_id=author_user_id,
        status=ConsultNoteStatus.captured,
        language=(language or "en"),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    logger.info("consult note %s created (status=%s)", note.id, note.status.value)
    return note


def store_audio(note: ConsultNote, audio: bytes, filename: str | None) -> str | None:
    """Best-effort archive of the consultation audio to object storage.

    Returns the storage key, or ``None`` if the object store was unreachable.
    A storage outage must not destroy the note — the caller surfaces the gap as
    a flag instead of pretending the audio was kept.
    """
    if not audio:
        return None
    key = build_storage_key(str(note.patient_id), filename or "consult.audio")
    try:
        put_object(key, audio, "application/octet-stream")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "consult note %s: audio archive failed (%s)", note.id, type(exc).__name__
        )
        return None
    return key


# ---------------------------------------------------------------------------
# Transcribe + draft
# ---------------------------------------------------------------------------
def process_note(
    db: Session,
    note: ConsultNote,
    *,
    audio: bytes | None = None,
    audio_filename: str | None = None,
    text: str | None = None,
) -> ConsultNote:
    """Run the note from ``captured`` through to ``drafted`` (or ``failed``).

    ``text`` (typed or pasted consultation content) wins when supplied; audio is
    transcribed otherwise. Failure is loud: the note lands in ``failed`` with a
    content-free ``error_reason`` rather than a confident, empty draft.
    """
    note.status = ConsultNoteStatus.transcribing
    db.add(note)
    db.commit()

    try:
        transcript, confidence, stub_transcript = _to_transcript(
            audio=audio, audio_filename=audio_filename, text=text, lang=note.language
        )
        if not transcript.strip():
            raise ValueError("no consultation content captured")

        payload = structure_note(
            transcript,
            language=note.language,
            use_llm=_use_llm(),
            stub_transcript=stub_transcript,
            confidence=confidence,
        )

        note.transcript = transcript
        note.sections = payload
        note.confidence = confidence
        note.error_reason = None
        note.status = ConsultNoteStatus.drafted
    except Exception as exc:  # noqa: BLE001 — fail loud, never fabricate
        note.status = ConsultNoteStatus.failed
        note.error_reason = f"consult drafting failed: {type(exc).__name__}"
        logger.warning(
            "consult note %s failed (%s)", note.id, type(exc).__name__
        )

    db.add(note)
    db.commit()
    db.refresh(note)
    logger.info("consult note %s -> status=%s", note.id, note.status.value)
    return note


def _use_llm() -> bool:
    """Real mode iff the LLM layer says a provider is actually configured."""
    try:
        from app.llm import service as llm

        return not llm.is_stub_mode()
    except Exception:  # noqa: BLE001 — absent/broken provider -> deterministic
        return False


def _to_transcript(
    *,
    audio: bytes | None,
    audio_filename: str | None,
    text: str | None,
    lang: str | None,
) -> tuple[str, float, bool]:
    """Return ``(transcript, confidence, came_from_stub)``."""
    if text and text.strip():
        # Typed/pasted content is exact — no transcription uncertainty.
        return text.strip(), 0.9, False
    if audio:
        from app.voice import transcribe

        result = transcribe(audio, filename=audio_filename, lang=lang)
        return (
            str(result.get("text") or ""),
            float(result.get("confidence") or 0.5),
            bool(result.get("stub")),
        )
    return "", 0.0, False


# ---------------------------------------------------------------------------
# Reading the stored payload
# ---------------------------------------------------------------------------
def _blank_sections() -> list[dict]:
    return [
        {"key": key, "title": SECTION_TITLES[key], "items": []}
        for key in SECTION_KEYS
    ]


def note_payload(note: ConsultNote) -> dict:
    """Normalize ``ConsultNote.sections`` into ``{sections, proposed_items}``.

    The column stores the full draft envelope
    ``{"sections": [...], "proposed_items": [...], "meta": {...}}`` so the
    doctor verifies exactly the items they were shown — re-deriving them later
    could drift. A bare list is tolerated for forward/backward compatibility.
    """
    stored = note.sections
    if isinstance(stored, list):
        return {"sections": stored, "proposed_items": [], "meta": {}}
    if isinstance(stored, dict):
        sections = stored.get("sections")
        return {
            "sections": sections if isinstance(sections, list) else _blank_sections(),
            "proposed_items": list(stored.get("proposed_items") or []),
            "meta": dict(stored.get("meta") or {}),
        }
    return {"sections": _blank_sections(), "proposed_items": [], "meta": {}}


# ---------------------------------------------------------------------------
# Verify (the human-in-the-loop gate)
# ---------------------------------------------------------------------------
def _kind_of(raw: str | None) -> ClinicalItemKind:
    try:
        return ClinicalItemKind(str(raw or "").strip().lower())
    except ValueError:
        return ClinicalItemKind.observation


def source_document(db: Session, note: ConsultNote) -> Document:
    """Get (or create) the Document row that represents this consultation.

    ClinicalItem requires a ``source_document_id``, and the citation rule says
    every fact must resolve to a source a doctor can open. The consultation is
    that source, so it is materialized as a ``typed_note`` DocumentReference
    holding the transcript — verified, because a human just confirmed it.
    """
    filename = _consult_filename(note.id)
    existing = db.execute(
        select(Document).where(
            Document.patient_id == note.patient_id, Document.filename == filename
        )
    ).scalars().first()
    if existing is not None:
        return existing

    transcript = note.transcript or ""
    document = Document(
        patient_id=note.patient_id,
        encounter_id=note.encounter_id,
        doc_type=DocumentType.typed_note,
        status=DocumentStatus.verified,
        filename=filename,
        content_type="text/plain",
        # Points at the captured audio when it was archived, so the citation can
        # offer the original recording alongside the transcript.
        storage_key=note.audio_key,
        size_bytes=len(transcript.encode("utf-8")),
        extracted_text=transcript,
        confidence=note.confidence,
    )
    db.add(document)
    db.flush()
    return document


def verify_note(
    db: Session,
    note: ConsultNote,
    *,
    item_indexes: list[int] | None = None,
    edits: dict | None = None,
) -> ConsultNote:
    """Accept the doctor's chosen proposed items into the patient's record.

    ``item_indexes`` selects into ``proposed_items`` (omit to accept all);
    ``edits`` maps an index to overrides ``{kind,label,value,unit}`` so the
    doctor can correct a misheard dose before it is stored. Accepted items become
    ``ClinicalItem`` rows with ``verified=True``, cited to the consultation
    document, and thereby feed the next visit's snapshot.
    """
    payload = note_payload(note)
    proposed = payload["proposed_items"]

    if item_indexes is None:
        chosen = list(range(len(proposed)))
    else:
        chosen = [i for i in item_indexes if 0 <= i < len(proposed)]

    normalized_edits: dict[int, dict] = {}
    for key, value in (edits or {}).items():
        if not isinstance(value, dict):
            continue
        try:
            normalized_edits[int(key)] = value
        except (TypeError, ValueError):
            continue

    document = source_document(db, note) if chosen else None

    created = 0
    for index in chosen:
        raw = dict(proposed[index])
        raw.update(
            {k: v for k, v in normalized_edits.get(index, {}).items() if v is not None}
        )
        label = str(raw.get("label") or "").strip()
        if not label:
            continue
        db.add(
            ClinicalItem(
                patient_id=note.patient_id,
                source_document_id=document.id,
                kind=_kind_of(raw.get("kind")),
                label=label[:512],
                value=(str(raw["value"])[:512] if raw.get("value") else None),
                unit=(str(raw["unit"])[:64] if raw.get("unit") else None),
                confidence=raw.get("confidence"),
                data={"source": "consult_note", "consult_note_id": str(note.id)},
                # A human just confirmed it — that is what verified means here.
                verified=True,
            )
        )
        created += 1

    note.status = ConsultNoteStatus.verified
    db.add(note)
    db.commit()
    db.refresh(note)
    logger.info(
        "consult note %s verified (items_accepted=%d)", note.id, created
    )
    return note
