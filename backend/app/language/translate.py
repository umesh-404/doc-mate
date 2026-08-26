"""Translation of the doctor's summary into EN / HI / regional languages.

Two paths, chosen by the same switch the rest of the backend uses
(``app.llm.is_stub_mode()``), so translation is offline-by-default and needs no
key:

* **Stub mode (default).** A bundled glossary maps the fixed section titles and
  common clinical phrase fragments into the target language. Everything not in
  the glossary passes through unchanged.
* **Real mode.** Routes through the ``app.llm`` layer (never a provider SDK
  here) with a translation prompt that is told to keep clinical values intact.
  Any failure degrades gracefully to the stub path.

SAFETY (PROJECT.md section 4 — NON-NEGOTIABLE): translation must never alter a
clinical value. Doses, lab values, units, dates, and drug names are preserved
verbatim. Every translated string is checked against its source: if a numeric /
dose token from the source is missing from the output, the ORIGINAL text is kept
instead. Structure, citations, severity, and trend are never touched.
"""

from __future__ import annotations

import logging
import re

from app.language import glossary

logger = logging.getLogger("docmate.language")

# Number-bearing tokens we must never lose or mutate during translation:
# "500mg", "7.8", "142", "1-0-1", "11.2 g/dL" (the number part), "40mcg".
_NUM_TOKEN = re.compile(r"\d+(?:[.\-]\d+)*\s*[%A-Za-z/µ]*")


def _numeric_tokens(text: str) -> list[str]:
    """Numeric / dose tokens that must survive translation untouched."""
    return [t.strip() for t in _NUM_TOKEN.findall(text or "") if any(c.isdigit() for c in t)]


def _values_preserved(source: str, candidate: str) -> bool:
    """True iff every numeric/dose token in ``source`` is present in ``candidate``."""
    for token in _numeric_tokens(source):
        # Compare on the digit-bearing core so trailing unit spacing is ignored.
        core = token.strip()
        if core and core not in candidate:
            return False
    return True


def is_stub_mode() -> bool:
    """Whether translation uses the offline glossary path (the default)."""
    try:
        from app.llm import service as llm

        return llm.is_stub_mode()
    except Exception:  # noqa: BLE001 — never let import issues break translation
        return True


# ---------------------------------------------------------------------------
# Stub (glossary) translation
# ---------------------------------------------------------------------------
def _glossary_translate(text: str, lang: str) -> str:
    """Replace known phrase fragments; leave numbers/doses/drug names intact."""
    if not text or lang == "en":
        return text
    out = text
    # Longest keys first so multi-word phrases win over their sub-words.
    for src in sorted(glossary.phrases(lang), key=len, reverse=True):
        if src in out:
            out = out.replace(src, glossary.phrases(lang)[src])
    return out


def _title_translate(title: str, lang: str) -> str:
    if lang == "en":
        return title
    mapped = glossary.section_titles(lang).get(title)
    return mapped or _glossary_translate(title, lang)


# ---------------------------------------------------------------------------
# Real (LLM) translation — routed through app.llm, never a provider SDK here.
# ---------------------------------------------------------------------------
def _llm_translate(text: str, lang: str) -> str | None:
    """Best-effort real-mode translation via the app.llm layer.

    Returns None on any failure so the caller falls back to the glossary path.
    Clinical values are protected by the post-check in :func:`translate_text`.
    """
    if not text.strip():
        return text
    try:
        from app.core.config import settings
        from app.llm import provider  # provider SDK stays confined to app.llm

        model = (settings.llm_model_reasoning or "").strip() or "gpt-4o-mini"
        system = (
            "You are a medical translation engine. Translate the user's text into "
            f"the language with ISO code '{lang}'. Preserve EXACTLY and unchanged: "
            "all numbers, doses, units, lab values, dates, and drug/medication "
            "names (do NOT translate or convert them). Do not add, remove, or "
            "interpret any clinical fact. Reply with a single JSON object: "
            '{"translation": "<translated text>"}.'
        )
        data = provider._completion_json(model, system, text)
        out = data.get("translation")
        return str(out) if isinstance(out, str) and out.strip() else None
    except Exception as exc:  # noqa: BLE001 — degrade to stub on any error
        logger.info("real-mode translate failed (%s); using glossary", type(exc).__name__)
        return None


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------
def translate_text(text: str, lang: str) -> str:
    """Translate a free-text string, guaranteeing clinical values are preserved."""
    if not text or lang == "en":
        return text

    candidate: str | None = None
    if not is_stub_mode():
        candidate = _llm_translate(text, lang)

    if candidate is None:
        candidate = _glossary_translate(text, lang)

    # SAFETY GATE: never emit a translation that dropped/mutated a clinical value.
    if not _values_preserved(text, candidate):
        logger.warning("translation altered a clinical value; keeping source text")
        return text
    return candidate


def translate_sections(sections: list[dict], lang: str) -> list[dict]:
    """Translate section titles + item text; keep everything else identical.

    Numbers, doses, drug names, citations, severity, trend, confidence, and
    verified flags are all carried through unchanged.
    """
    out: list[dict] = []
    for section in sections:
        new_items = []
        for item in section.get("items", []) or []:
            new_item = dict(item)
            new_item["text"] = translate_text(str(item.get("text", "")), lang)
            new_items.append(new_item)
        out.append(
            {
                "key": section.get("key"),
                "title": _title_translate(str(section.get("title", "")), lang),
                "items": new_items,
            }
        )
    return out


def stub_note(lang: str) -> str:
    """Human-readable note marking glossary-based (stub) translation output."""
    return glossary.stub_note(lang)
