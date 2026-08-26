"""Bundled offline glossaries for stub-mode translation + simplification.

Loads the per-language JSON packs in ``app/language/data/``. These power the
deterministic, offline stub translation path: fixed section titles and common
clinical phrase fragments are mapped to Hindi / Tamil / Telugu, while everything else —
crucially numbers, doses, units, drug and lab names — passes through UNCHANGED
(PROJECT.md section 4: never alter a clinical value).

No network, no key, no LLM. This is the default path.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SUPPORTED_LANGS = ("en", "hi", "ta", "te")

_DATA_DIR = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=len(SUPPORTED_LANGS))
def load_pack(lang: str) -> dict:
    """Load and cache a language pack; falls back to English for unknowns."""
    code = (lang or "en").strip().lower()
    if code not in SUPPORTED_LANGS:
        code = "en"
    path = _DATA_DIR / f"{code}.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def section_titles(lang: str) -> dict[str, str]:
    return dict(load_pack(lang).get("section_titles", {}))


def phrases(lang: str) -> dict[str, str]:
    return dict(load_pack(lang).get("phrases", {}))


def plain_lead(lang: str) -> str:
    return str(load_pack(lang).get("plain_lead", ""))


def plain_labels(lang: str) -> dict[str, str]:
    return dict(load_pack(lang).get("plain_labels", {}))


def stub_note(lang: str) -> str:
    return str(load_pack(lang).get("stub_note", ""))
