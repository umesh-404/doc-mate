"""Voice routes: transcribe spoken intake notes.

Reception can dictate a patient's complaint/history instead of typing. The audio
is transcribed on-device (faster-whisper) when available, otherwise a
deterministic offline stub so the flow always works. No audio or PHI is logged.

Contract v2:
  POST /voice/transcribe (multipart: audio, optional lang)
    -> {text, lang, confidence, stub}
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.security import get_current_user
from app.voice import transcribe as run_transcribe

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe", dependencies=[Depends(get_current_user)])
async def transcribe_audio(
    audio: Annotated[UploadFile, File()],
    lang: Annotated[str | None, Form()] = None,
) -> dict:
    """Transcribe an uploaded intake-audio clip.

    Returns ``{text, lang, confidence, stub}``. ``stub`` is True when the
    deterministic offline fallback produced the text (no model available).
    """
    data = await audio.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio upload"
        )
    return run_transcribe(data, filename=audio.filename, lang=lang)
