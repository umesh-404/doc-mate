"""Medical-coding lookup: map clinical labels onto ICD-11 / NAMASTE codes.

Offline and deterministic — all data is bundled under ``app/coding/data`` and no
external terminology service is called (PROJECT.md: stub-safe, no network).

Honesty rules (PROJECT.md section 4):
- Never fabricate a code. If nothing matches, return an empty list.
- Always cite the code ``system`` truthfully ("ICD-11" or "NAMASTE").

Matching is intentionally simple and case-insensitive: exact/substring against
each entry's display text and curated aliases. This favours precision on the
common outpatient vocabulary the demo uses rather than broad NLP recall.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.coding.data.icd11 import ICD11_ENTRIES
from app.coding.data.namaste import NAMASTE_ENTRIES

# Canonical system identifiers surfaced in the API and FHIR codings.
SYSTEM_ICD11 = "ICD-11"
SYSTEM_NAMASTE = "NAMASTE"

# Public code system URIs used when emitting FHIR Coding.system values.
SYSTEM_URI = {
    SYSTEM_ICD11: "http://id.who.int/icd/release/11/mms",
    SYSTEM_NAMASTE: "https://namaste.ayush.gov.in",
}


@dataclass(frozen=True)
class Code:
    """A single resolved medical code."""

    system: str
    code: str
    display: str

    def as_dict(self) -> dict[str, str]:
        return {"system": self.system, "code": self.code, "display": self.display}

    def system_uri(self) -> str:
        return SYSTEM_URI.get(self.system, self.system)


@dataclass(frozen=True)
class _Entry:
    system: str
    code: str
    display: str
    # Lowercase match terms (display text is always included).
    terms: tuple[str, ...] = field(default=())

    def to_code(self) -> Code:
        return Code(system=self.system, code=self.code, display=self.display)


def _build(system: str, rows: list[tuple[str, str, list[str]]]) -> list[_Entry]:
    entries: list[_Entry] = []
    for code, display, aliases in rows:
        terms = {display.lower(), *(a.lower() for a in aliases)}
        entries.append(
            _Entry(system=system, code=code, display=display, terms=tuple(terms))
        )
    return entries


# Flat, immutable index built once at import time (pure Python, no I/O).
_INDEX: list[_Entry] = [
    *_build(SYSTEM_ICD11, ICD11_ENTRIES),
    *_build(SYSTEM_NAMASTE, NAMASTE_ENTRIES),
]


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def map_condition(label: str) -> list[Code]:
    """Return codes matching a clinical label (case-insensitive, substring).

    Matches against both ICD-11 and NAMASTE. An entry matches when any of its
    curated terms is a substring of the label, or the label is a substring of a
    term (handles both "Type 2 diabetes mellitus" and a terse "diabetes").
    Returns an empty list when nothing matches — never a fabricated code.

    ICD-11 matches are returned before NAMASTE ones; within a system, longer
    (more specific) term matches rank first.
    """
    if not label or not label.strip():
        return []
    query = _norm(label)

    scored: list[tuple[int, int, int, Code]] = []
    for order, entry in enumerate(_INDEX):
        best = 0
        for term in entry.terms:
            if term in query or query in term:
                best = max(best, len(term))
        if best:
            # ICD-11 first (system_rank 0), then by longer (more specific)
            # term match, then by bundled order for a stable tiebreak.
            system_rank = 0 if entry.system == SYSTEM_ICD11 else 1
            scored.append((system_rank, -best, order, entry.to_code()))

    if not scored:
        return []

    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    # De-duplicate on (system, code) preserving order.
    seen: set[tuple[str, str]] = set()
    result: list[Code] = []
    for _, _, _, code in scored:
        key = (code.system, code.code)
        if key not in seen:
            seen.add(key)
            result.append(code)
    return result


def primary_code(label: str, system: str | None = None) -> Code | None:
    """Return the single best code for a label, optionally within one system."""
    codes = map_condition(label)
    if system:
        codes = [c for c in codes if c.system == system]
    return codes[0] if codes else None


def search(term: str, system: str | None = None) -> list[Code]:
    """Free-text search over the code lists.

    ``system`` filters to "icd11"/"ICD-11" or "namaste"/"NAMASTE". Matches on
    code, display text, or any alias. Returns [] when nothing matches.
    """
    if not term or not term.strip():
        return []
    q = _norm(term)
    want = _canonical_system(system)

    results: list[Code] = []
    seen: set[tuple[str, str]] = set()
    for entry in _INDEX:
        if want and entry.system != want:
            continue
        haystack = (entry.code.lower(), *entry.terms)
        if any(q in h or h in q for h in haystack):
            key = (entry.system, entry.code)
            if key not in seen:
                seen.add(key)
                results.append(entry.to_code())
    return results


def _canonical_system(system: str | None) -> str | None:
    if not system:
        return None
    s = system.strip().lower().replace("-", "").replace("_", "")
    if s in {"icd11", "icd"}:
        return SYSTEM_ICD11
    if s in {"namaste", "ayush"}:
        return SYSTEM_NAMASTE
    return None


def coverage() -> dict[str, int]:
    """Return the number of bundled entries per system (for reporting/tests)."""
    counts: dict[str, int] = {}
    for entry in _INDEX:
        counts[entry.system] = counts.get(entry.system, 0) + 1
    return counts
