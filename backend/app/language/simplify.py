"""Plain-language patient-friendly narrative of the doctor's summary.

Turns the structured, citation-backed snapshot into a short, simplified
paragraph a patient (not a clinician) can understand — still grounded in the
same facts, still NO diagnosis or advice (PROJECT.md section 4), and explicitly
labelled informational.

Stub mode (default): a templated paragraph assembled from the summary sections.
Real mode: routed through the ``app.llm`` layer with a simplification prompt,
degrading to the template on any failure. Clinical values in the text are left
as-is (the template quotes item text verbatim; the real path is instructed to
keep numbers/doses intact).
"""

from __future__ import annotations

import logging

from app.language import glossary, translate

logger = logging.getLogger("docmate.language")


def _template_plain(sections: list[dict], lang: str) -> str:
    """Deterministic, offline plain-language paragraph from the sections."""
    labels = glossary.plain_labels(lang)
    parts: list[str] = [glossary.plain_lead(lang)]

    for section in sections:
        key = section.get("key")
        items = [str(it.get("text", "")).strip() for it in (section.get("items") or [])]
        items = [t for t in items if t]
        if not items:
            continue
        label = labels.get(key, str(section.get("title", key)))
        # Translate the human label + free text via the glossary-safe helper so
        # numbers/doses are preserved and Hindi/Tamil/Telugu output reads naturally.
        body = "; ".join(translate.translate_text(t, lang) for t in items)
        parts.append(f"{label}: {body}.")

    return " ".join(p for p in parts if p).strip()


def _llm_plain(sections: list[dict], lang: str) -> str | None:
    """Best-effort real-mode simplification via app.llm; None on failure."""
    try:
        import json

        from app.core.config import settings
        from app.llm import provider  # provider SDK confined to app.llm

        model = (settings.llm_model_reasoning or "").strip() or "gpt-4o-mini"
        system = (
            "You rewrite a structured clinical summary as a short, simple, "
            "patient-friendly paragraph in the language with ISO code "
            f"'{lang}'. Simplify medical jargon into everyday words. Keep all "
            "numbers, doses, and dates exactly as given. Do NOT state or imply a "
            "diagnosis, prognosis, or treatment advice — only describe what the "
            "records contain. Begin by noting it is informational only. Reply "
            'with a single JSON object: {"text": "<paragraph>"}.'
        )
        payload = json.dumps({"sections": sections}, ensure_ascii=False, default=str)
        data = provider._completion_json(model, system, payload)
        out = data.get("text")
        return str(out) if isinstance(out, str) and out.strip() else None
    except Exception as exc:  # noqa: BLE001
        logger.info("real-mode simplify failed (%s); using template", type(exc).__name__)
        return None


def plain_language(sections: list[dict], lang: str) -> str:
    """Return a patient-friendly narrative of ``sections`` in ``lang``."""
    if not translate.is_stub_mode():
        out = _llm_plain(sections, lang)
        if out:
            return out
    return _template_plain(sections, lang)
