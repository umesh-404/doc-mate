"""Voice intake layer: transcribe spoken reception notes, offline-safe.

Public surface:

* ``transcribe(audio, filename=None, lang=None)`` -> ``{text, lang, confidence,
  stub}``. Uses on-device ``faster-whisper`` when available, otherwise a
  deterministic canned transcription so intake works with no deps / no GPU /
  offline.
"""

from __future__ import annotations

from app.voice.transcribe import transcribe

__all__ = ["transcribe"]
