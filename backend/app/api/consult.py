"""Consultation-scribe routes (contract v3).

Closes Doc-mate's loop: everything else covers what happened *before* the
consultation; these routes capture the consultation itself, draft a note from
it, and — only once a doctor verifies — fold it into the record that feeds the
next visit's snapshot.

    POST /patients/{patient_id}/consult   (multipart: audio?, text?, language?)
    GET  /patients/{patient_id}/consult
    GET  /consult/{note_id}
    POST /consult/{note_id}/verify

Processing is **inline**: the POST transcribes and drafts before responding, so
a successful capture comes back already ``drafted`` (no polling). It falls to
``failed`` with a content-free reason if drafting could not complete.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.consult import pipeline
from app.core.security import CurrentUser, get_current_user
from app.db.models import ConsultNote, ConsultNoteStatus, Patient
from app.db.session import get_db
from app.schemas.consult import (
    ConsultNoteDetail,
    ConsultNoteRead,
    ConsultVerifyRequest,
)

router = APIRouter(tags=["consult"])


def _detail(note: ConsultNote) -> ConsultNoteDetail:
    payload = pipeline.note_payload(note)
    return ConsultNoteDetail(
        id=note.id,
        patient_id=note.patient_id,
        encounter_id=note.encounter_id,
        status=note.status,
        language=note.language,
        confidence=note.confidence,
        created_at=note.created_at,
        transcript=note.transcript,
        error=note.error_reason,
        sections=payload["sections"],
        proposed_items=payload["proposed_items"],
    )


def _get_note(db: Session, note_id: uuid.UUID) -> ConsultNote:
    note = db.get(ConsultNote, note_id)
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Consult note not found"
        )
    return note


@router.post(
    "/patients/{patient_id}/consult",
    response_model=ConsultNoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def capture_consult(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    audio: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
) -> ConsultNoteRead:
    """Capture a consultation and return the drafted note.

    Supply spoken audio, typed text, or both (text wins). The note is
    transcribed and structured inline, so the response status is ``drafted`` on
    success and ``failed`` — with a reason — when it could not be drafted.
    """
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    audio_bytes = await audio.read() if audio is not None else b""
    if not audio_bytes and not (text or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide consultation audio or text",
        )

    note = pipeline.create_note(
        db,
        patient_id=patient_id,
        author_user_id=user.id,
        language=(language or patient.preferred_language or "en"),
    )

    if audio_bytes:
        # Best-effort archive; a storage outage must not lose the note.
        note.audio_key = pipeline.store_audio(note, audio_bytes, audio.filename)

    note = pipeline.process_note(
        db,
        note,
        audio=audio_bytes or None,
        audio_filename=audio.filename if audio is not None else None,
        text=text,
    )
    return ConsultNoteRead.model_validate(note)


@router.get(
    "/patients/{patient_id}/consult",
    response_model=list[ConsultNoteRead],
    dependencies=[Depends(get_current_user)],
)
def list_consult_notes(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[ConsultNote]:
    """All consultation notes for a patient, most recent first."""
    stmt = (
        select(ConsultNote)
        .where(ConsultNote.patient_id == patient_id)
        .order_by(ConsultNote.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get(
    "/consult/{note_id}",
    response_model=ConsultNoteDetail,
    dependencies=[Depends(get_current_user)],
)
def get_consult_note(
    note_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ConsultNoteDetail:
    return _detail(_get_note(db, note_id))


@router.post(
    "/consult/{note_id}/verify",
    response_model=ConsultNoteDetail,
    dependencies=[Depends(get_current_user)],
)
def verify_consult_note(
    note_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    payload: ConsultVerifyRequest | None = None,
) -> ConsultNoteDetail:
    """The human-in-the-loop gate.

    Marks the note ``verified`` and writes the accepted proposed items into the
    record as real ``ClinicalItem`` rows (``verified=True``), cited to a
    consultation Document. Nothing from a consultation reaches the patient's
    record by any other path.
    """
    note = _get_note(db, note_id)
    if note.status == ConsultNoteStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Consult note failed to draft and cannot be verified",
        )

    note = pipeline.verify_note(
        db,
        note,
        item_indexes=payload.item_indexes if payload else None,
        edits=payload.edits if payload else None,
    )
    return _detail(note)
