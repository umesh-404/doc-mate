"""Deterministic faithfulness / grounding check for generated summaries.

For every generated summary line we verify that its text is actually supported
by the source it cites (PROJECT.md sections 3, 4: everything is cited; nothing
is invented). The check is fully deterministic — lexical (content-token)
overlap plus exact numeric-value matching between the summary line and the text
of its cited source facts — so it runs identically with the LLM in stub mode
and needs no provider or network.

This is a heuristic grounding signal, NOT a full natural-language-inference
model. It reliably catches lines that introduce entities or numbers absent from
the cited source (the fabrication case we most care about), while accepting
lines that paraphrase their source.
"""

from __future__ import annotations

import re

GROUNDING_METHOD = "lexical+numeric overlap v1"

# Sections whose items are not required to be source-grounded facts.
_UNGROUNDED_SECTIONS = {"flags"}

# Overlap ratio (content tokens of the line found in the source) at/above which
# a line is considered supported.
_TOKEN_THRESHOLD = 0.5

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_WORD_RE = re.compile(r"[a-z0-9]+")

# Connective / boilerplate words that carry no clinical content — excluded so a
# line is judged on its clinical tokens, not its phrasing.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "of", "for", "to", "and", "or", "with", "without",
        "on", "in", "at", "by", "is", "are", "was", "were", "be", "been",
        "as", "from", "this", "that", "these", "those", "review", "presenting",
        "patient", "current", "recent", "per", "day", "days", "mg", "mcg",
        "ml", "unit", "units",
    }
)


def _content_tokens(text: str) -> list[str]:
    return [
        t
        for t in _WORD_RE.findall((text or "").lower())
        if t not in _STOPWORDS and not t.isdigit()
    ]


def _numbers(text: str) -> set[str]:
    # Normalize trailing-zero noise so "7.80" and "7.8" match.
    out: set[str] = set()
    for raw in _NUM_RE.findall(text or ""):
        if "." in raw:
            raw = raw.rstrip("0").rstrip(".")
        out.add(raw)
    return out


def _source_text_for(citations: list[dict], context_by_doc: dict[str, str]) -> str:
    """Concatenate the text of every cited source document's facts."""
    parts: list[str] = []
    for cite in citations or []:
        doc_id = str(cite.get("document_id"))
        if doc_id in context_by_doc:
            parts.append(context_by_doc[doc_id])
    return " ".join(parts)


def _fact_text(fact: dict) -> str:
    """Flatten a context fact into a plain text blob for overlap checks."""
    parts = [
        str(fact.get("label") or ""),
        str(fact.get("value") or ""),
        str(fact.get("unit") or ""),
    ]
    return " ".join(p for p in parts if p)


def _index_context(context: list[dict]) -> dict[str, str]:
    """Map document_id -> combined text of all facts citing that document."""
    index: dict[str, list[str]] = {}
    for fact in context or []:
        doc_id = str(fact.get("document_id"))
        index.setdefault(doc_id, []).append(_fact_text(fact))
    return {k: " ".join(v) for k, v in index.items()}


def assess_item(item: dict, source_text: str) -> tuple[bool, str | None]:
    """Return ``(grounded, note)`` for a single summary line vs its source."""
    if not source_text.strip():
        return False, "No cited source text available to verify this line."

    line_tokens = _content_tokens(item.get("text", ""))
    src_tokens = set(_content_tokens(source_text))

    # Numeric faithfulness: every number in the line must appear in the source.
    line_nums = _numbers(item.get("text", ""))
    src_nums = _numbers(source_text)
    missing_nums = sorted(line_nums - src_nums)
    if missing_nums:
        return (
            False,
            "Value(s) not found in cited source: " + ", ".join(missing_nums),
        )

    if not line_tokens:
        # No content tokens and numbers already matched -> treat as grounded.
        return True, None

    overlap = sum(1 for t in line_tokens if t in src_tokens)
    ratio = overlap / len(line_tokens)
    if ratio < _TOKEN_THRESHOLD:
        return (
            False,
            "Line content not supported by cited source "
            f"(overlap {ratio:.0%}).",
        )
    return True, None


def check_grounding(
    sections: list[dict], context: list[dict]
) -> tuple[list[dict], dict]:
    """Annotate summary items with grounding and compute an overall score.

    Mutates a copy of ``sections``: every non-flags item gains ``grounded``
    (bool) and, when unsupported, a short ``grounding_note``. Returns the
    updated sections plus a grounding dict::

        {"score": float 0..1, "method": str, "unsupported_count": int}

    ``score`` is the fraction of non-flags items judged grounded (1.0 when
    there are no such items).
    """
    context_by_doc = _index_context(context)

    graded = 0
    grounded = 0
    out_sections: list[dict] = []
    for section in sections:
        key = section.get("key")
        new_items: list[dict] = []
        for item in section.get("items", []):
            item = dict(item)
            if key in _UNGROUNDED_SECTIONS:
                new_items.append(item)
                continue
            source_text = _source_text_for(item.get("citations", []), context_by_doc)
            ok, note = assess_item(item, source_text)
            item["grounded"] = ok
            item["grounding_note"] = None if ok else note
            graded += 1
            if ok:
                grounded += 1
            new_items.append(item)
        out_sections.append({**section, "items": new_items})

    score = 1.0 if graded == 0 else round(grounded / graded, 4)
    grounding = {
        "score": score,
        "method": GROUNDING_METHOD,
        "unsupported_count": graded - grounded,
    }
    return out_sections, grounding
