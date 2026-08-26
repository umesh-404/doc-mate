"""Deterministic, offline scorers for generated patient summaries.

Three axes, each returning a score in ``0..1`` plus a ``details`` dict that
explains exactly how the number was reached (so a score is always defensible
and auditable, PROJECT.md section 4).

Definitions
-----------
**faithfulness** — fraction of non-``flags`` summary items that are supported by
the facts of the source document(s) they cite. Delegates the per-item judgement
to :func:`app.safety.grounding.check_grounding` (lexical content-token overlap
>= 50% AND every number in the line present in the cited source). Any number in
a line that is absent from its cited source makes that line unsupported — this
is the fabrication case we most care about. Score = ``supported / graded``;
``1.0`` when there is nothing to grade.

**completeness** — fraction of the patient's *important* clinical facts that the
summary actually surfaces. "Important" is defined explicitly (see
:func:`important_facts`) as:

  * every ``allergy`` fact (always important — safety critical),
  * every ``condition`` fact (chronic/active problems),
  * every **verified** ``medication`` fact (unverified extractions are proposals,
    not yet record, so they are not required),
  * every ``observation`` (lab/vital) that is either **out of the typical range**
    (per :mod:`app.safety.alerts` thresholds) or is the **most recent** value for
    its label.

A fact counts as covered when some summary item's text (any section, including
``flags`` — surfacing a gap counts as surfacing the fact) contains at least 60%
of the content tokens of the fact's label. Score = ``covered / important``;
``1.0`` when the patient has no important facts. ``details["missed"]`` lists
every uncovered fact — omission is the dominant failure mode in clinical
summarisation, so naming the misses is the point of this metric.

**conciseness** — information density, bounded: how many important facts the
summary conveys per 100 words of summary text.
``density = covered_facts / (words / 100)``; score = ``min(1, density / 6.0)``
where ``6.0`` facts per 100 words (~17 words per fact) is the target density for
a snapshot readable in under a minute. Because the numerator counts only
*covered* facts, cutting content to shorten the summary lowers the numerator as
fast as the denominator — terseness that drops facts is not rewarded.

**overall** — weighted mean, faithfulness weighted highest because a confident
wrong line is worse than a missing one:
``0.50 * faithfulness + 0.30 * completeness + 0.20 * conciseness``.

Limitation: this is deterministic *lexical* scoring — a cheap, reproducible
proxy for human or NLI-based evaluation, not a replacement for it. It can be
fooled by heavy paraphrase (false omission) or by a line that reuses source
tokens in a wrong relation (false support).
"""

from __future__ import annotations

import re

from app.safety.alerts import _LAB_RANGES  # neutral out-of-range thresholds
from app.safety.grounding import check_grounding

EVAL_METHOD = "deterministic v1"

# Weighted combination for the overall score (must sum to 1.0).
OVERALL_WEIGHTS = {"faithfulness": 0.50, "completeness": 0.30, "conciseness": 0.20}

# Fraction of a fact label's content tokens that must appear in a summary item
# for that item to count as surfacing the fact.
_COVERAGE_THRESHOLD = 0.6

# Target information density: important facts conveyed per 100 words.
_TARGET_FACTS_PER_100_WORDS = 6.0

_WORD_RE = re.compile(r"[a-z0-9]+")

# Label words that carry no identifying content of their own.
_LABEL_STOPWORDS = frozenset(
    {"of", "the", "a", "an", "and", "or", "test", "level", "levels", "serum",
     "blood", "total"}
)


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall((text or "").lower())
            if t not in _LABEL_STOPWORDS]


def _all_items(sections: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for section in sections or []:
        for item in section.get("items") or []:
            out.append(item)
    return out


def _word_count(sections: list[dict] | None) -> int:
    return sum(
        len(_WORD_RE.findall(str(item.get("text") or "").lower()))
        for item in _all_items(sections)
    )


def _parse_float(value) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _is_out_of_range(fact: dict) -> bool:
    """True when an observation sits outside the neutral typical range."""
    label = str(fact.get("label") or "").lower()
    value = _parse_float(fact.get("value"))
    if value is None:
        return False
    for rng in _LAB_RANGES:
        if rng["match"] not in label:
            continue
        if "high" in rng and value > rng["high"]:
            return True
        if "low" in rng and value < rng["low"]:
            return True
        return False
    return False


def _fact_key(fact: dict) -> str:
    return f"{fact.get('kind')}|{str(fact.get('label') or '').strip().lower()}"


# ---------------------------------------------------------------------------
# Important-fact selection (the completeness ground truth)
# ---------------------------------------------------------------------------
def important_facts(context: list[dict] | None) -> list[dict]:
    """Select the facts a summary is *required* to surface.

    See the module docstring for the rule. Returns the selected context facts
    (same dicts), each annotated under ``_reason`` with why it was selected.
    """
    context = context or []
    selected: list[dict] = []

    # Most-recent observation per label. ``gather_context`` already returns
    # facts newest-first, so the first occurrence of a label is the latest.
    seen_labels: set[str] = set()

    for fact in context:
        kind = str(fact.get("kind") or "")
        label_key = str(fact.get("label") or "").strip().lower()
        reason: str | None = None

        if kind == "allergy":
            reason = "allergy (always required)"
        elif kind == "condition":
            reason = "active/chronic condition"
        elif kind == "medication" and bool(fact.get("verified")):
            reason = "verified medication"
        elif kind == "observation":
            if _is_out_of_range(fact):
                reason = "lab outside typical range"
            elif label_key not in seen_labels:
                reason = "most recent value for this label"

        if kind == "observation":
            seen_labels.add(label_key)

        if reason:
            selected.append({**fact, "_reason": reason})
    return selected


# ---------------------------------------------------------------------------
# Faithfulness
# ---------------------------------------------------------------------------
def score_faithfulness(
    sections: list[dict] | None, context: list[dict] | None
) -> tuple[float, dict]:
    """Fraction of non-``flags`` items supported by their cited source facts."""
    sections = sections or []
    context = context or []
    graded_sections, grounding = check_grounding(sections, context)

    supported: list[str] = []
    unsupported: list[dict] = []
    for section in graded_sections:
        for item in section.get("items") or []:
            if "grounded" not in item:  # flags section — not graded
                continue
            text = str(item.get("text") or "")
            if item["grounded"]:
                supported.append(text)
            else:
                unsupported.append(
                    {
                        "section": section.get("key"),
                        "text": text,
                        "reason": item.get("grounding_note"),
                    }
                )

    graded = len(supported) + len(unsupported)
    score = 1.0 if graded == 0 else round(len(supported) / graded, 4)
    details = {
        "graded_items": graded,
        "supported_count": len(supported),
        "unsupported_count": len(unsupported),
        "unsupported": unsupported,
        "supported": supported,
        "grounding_method": grounding["method"],
    }
    return score, details


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------
def _fact_is_covered(fact: dict, item_token_sets: list[set[str]]) -> bool:
    label_tokens = _tokens(str(fact.get("label") or ""))
    if not label_tokens:
        return False
    needed = max(1, int(round(_COVERAGE_THRESHOLD * len(label_tokens))))
    for tokens in item_token_sets:
        if sum(1 for t in label_tokens if t in tokens) >= needed:
            return True
    return False


def score_completeness(
    sections: list[dict] | None, context: list[dict] | None
) -> tuple[float, dict]:
    """Fraction of the patient's important facts surfaced by the summary."""
    facts = important_facts(context)
    items = _all_items(sections)
    item_token_sets = [set(_tokens(str(i.get("text") or ""))) for i in items]

    covered: list[dict] = []
    missed: list[dict] = []
    for fact in facts:
        entry = {
            "kind": fact.get("kind"),
            "label": fact.get("label"),
            "value": fact.get("value"),
            "unit": fact.get("unit"),
            "date": fact.get("date"),
            "reason_important": fact.get("_reason"),
            "citation_label": fact.get("citation_label"),
        }
        if _fact_is_covered(fact, item_token_sets):
            covered.append(entry)
        else:
            missed.append(entry)

    total = len(facts)
    score = 1.0 if total == 0 else round(len(covered) / total, 4)
    details = {
        "important_fact_count": total,
        "covered_count": len(covered),
        "missed_count": len(missed),
        "missed": missed,
        "covered": covered,
        "definition": (
            "important = all allergies, all conditions, all verified "
            "medications, and every observation that is out of typical range "
            "or the most recent value for its label"
        ),
    }
    return score, details


# ---------------------------------------------------------------------------
# Conciseness
# ---------------------------------------------------------------------------
def score_conciseness(
    sections: list[dict] | None, covered_fact_count: int
) -> tuple[float, dict]:
    """Bounded information density: covered facts per 100 words of summary."""
    words = _word_count(sections)
    if words == 0:
        # Nothing written. Only a summary that also had nothing to say is
        # "perfectly concise"; otherwise it conveys no facts at all.
        score = 1.0 if covered_fact_count == 0 else 0.0
        return score, {
            "word_count": 0,
            "covered_fact_count": covered_fact_count,
            "facts_per_100_words": 0.0,
            "target_facts_per_100_words": _TARGET_FACTS_PER_100_WORDS,
            "note": "Summary contains no text.",
        }

    density = covered_fact_count / (words / 100.0)
    score = round(min(1.0, density / _TARGET_FACTS_PER_100_WORDS), 4)
    return score, {
        "word_count": words,
        "covered_fact_count": covered_fact_count,
        "facts_per_100_words": round(density, 3),
        "target_facts_per_100_words": _TARGET_FACTS_PER_100_WORDS,
        "note": (
            "Density counts only facts the summary actually conveys, so "
            "shortening by dropping facts does not raise this score."
        ),
    }


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------
def score_overall(
    faithfulness: float, completeness: float, conciseness: float
) -> float:
    return round(
        OVERALL_WEIGHTS["faithfulness"] * faithfulness
        + OVERALL_WEIGHTS["completeness"] * completeness
        + OVERALL_WEIGHTS["conciseness"] * conciseness,
        4,
    )


def score_summary(
    sections: list[dict] | None, context: list[dict] | None
) -> dict:
    """Score one summary on all three axes.

    Returns::

        {
          "faithfulness": float, "completeness": float,
          "conciseness": float, "overall": float,
          "method": str,
          "details": {"faithfulness": {...}, "completeness": {...},
                       "conciseness": {...}, "weights": {...}},
        }

    Safe on empty/degenerate input: an empty summary over an empty context
    scores 1.0 on every axis (nothing to hallucinate, nothing to omit).
    """
    sections = sections or []
    context = context or []

    faith, faith_details = score_faithfulness(sections, context)
    comp, comp_details = score_completeness(sections, context)
    if comp_details["important_fact_count"] == 0:
        # Nothing was required of this summary, so density is not meaningful;
        # do not punish a summary for facts the record never contained.
        conc, conc_details = 1.0, {
            "word_count": _word_count(sections),
            "covered_fact_count": 0,
            "facts_per_100_words": 0.0,
            "target_facts_per_100_words": _TARGET_FACTS_PER_100_WORDS,
            "note": "No important facts on record — density not applicable.",
        }
    else:
        conc, conc_details = score_conciseness(
            sections, comp_details["covered_count"]
        )
    overall = score_overall(faith, comp, conc)

    return {
        "faithfulness": faith,
        "completeness": comp,
        "conciseness": conc,
        "overall": overall,
        "method": EVAL_METHOD,
        "details": {
            "faithfulness": faith_details,
            "completeness": comp_details,
            "conciseness": conc_details,
            "weights": dict(OVERALL_WEIGHTS),
        },
    }
