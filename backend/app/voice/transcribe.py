"""Speech-to-text for spoken intake notes — offline-safe.

Two paths:

* **Real mode** — uses ``faster-whisper`` IF the library is installed AND a model
  can be loaded (``small`` / ``base``). Runs fully on-prem (no cloud, no key),
  which fits the government-hospital privacy story: patient audio never leaves
  the box.
* **Stub mode (default, and any time the lib/model is unavailable)** — returns a
  deterministic canned transcription derived from the audio's size/filename, so
  the intake flow works with no dependencies, no GPU, and no internet.

Never raises for a missing library or model — it degrades to the stub. No audio
bytes or PHI are ever logged.
"""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger("docmate.voice")

# Canned intake phrasings for the deterministic stub. Chosen to look like plausible
# reception dictation; picked by a stable hash of the audio so runs reproduce.
_CANNED = [
    "Patient reports fever and cough for the past three days.",
    "Complains of chest pain and shortness of breath since morning.",
    "Here for routine diabetes follow-up; no new complaints.",
    "Severe headache and dizziness for two days, no vomiting.",
    "Follow-up for blood pressure review; brought previous prescriptions.",
    "Abdominal pain and loss of appetite for one week.",
]

# Model preference order for the real path (smallest first for CPU/offline).
_MODEL_PREFERENCE = ("small", "base")


def _canned_for(audio: bytes, filename: str | None) -> str:
    seed = hashlib.sha256((filename or "").encode("utf-8") + (audio or b"")[:4096]).digest()
    return _CANNED[int.from_bytes(seed[:4], "big") % len(_CANNED)]


def _try_faster_whisper(audio: bytes, lang: str | None) -> dict | None:
    """Attempt a real on-device transcription. Returns None if unavailable."""
    try:
        import io
        import os
        import tempfile

        from faster_whisper import WhisperModel  # optional heavy dep
    except Exception:
        return None

    model = None
    for size in _MODEL_PREFERENCE:
        try:
            # Loads from local cache if the model is already present; will attempt
            # a download otherwise (which fails cleanly offline -> we fall back).
            model = WhisperModel(size, device="cpu", compute_type="int8")
            break
        except Exception as exc:  # noqa: BLE001
            logger.info("whisper model '%s' unavailable (%s)", size, type(exc).__name__)
            model = None
    if model is None:
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
            tmp.write(audio)
            tmp_path = tmp.name
        segments, info = model.transcribe(
            tmp_path,
            language=(lang if lang and lang != "auto" else None),
            beam_size=1,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        detected = getattr(info, "language", None) or lang or "en"
        prob = getattr(info, "language_probability", None)
        confidence = round(float(prob), 3) if isinstance(prob, (int, float)) else 0.9
        _ = io  # keep import explicit
        return {
            "text": text,
            "lang": detected,
            "confidence": confidence,
            "stub": False,
        }
    except Exception as exc:  # noqa: BLE001 — any failure -> stub fallback
        logger.info("faster-whisper transcribe failed (%s)", type(exc).__name__)
        return None
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def transcribe(audio: bytes, filename: str | None = None, lang: str | None = None) -> dict:
    """Transcribe spoken intake audio.

    Returns ``{text, lang, confidence, stub}``. Tries on-device faster-whisper
    first; falls back to a deterministic canned transcription so the flow always
    works offline.
    """
    result = _try_faster_whisper(audio, lang)
    if result is not None:
        return result

    return {
        "text": _canned_for(audio, filename),
        "lang": (lang or "en"),
        "confidence": 0.5,
        "stub": True,
    }
