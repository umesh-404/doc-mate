"""Offline drug-drug interaction and drug-allergy checker.

Backed entirely by a small bundled reference dataset
(:mod:`app.safety.data`) — there is NO external API call, so it works with no
internet and no patient data ever leaves the system (PROJECT.md sections 4, 5).

This is a *surfacing* tool: it flags well-known interaction and allergy pairs so
a human clinician can review them. It is intentionally conservative, matches on
loose (case-insensitive, dose-stripped) drug names, and never recommends a
course of action.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "data" / "interactions.json"

# Dose/frequency/route noise stripped before matching drug names.
_DOSE_RE = re.compile(
    r"\b\d+(\.\d+)?\s*"
    r"(mg|mcg|µg|ug|g|ml|iu|units?|%|tablet|tab|cap|capsule|drops?|"
    r"puffs?|inhaler|injection|inj|syrup|susp|od|bd|tds|qid|prn|hs|"
    r"once|twice|daily|weekly)\b",
    re.IGNORECASE,
)
_FREQ_RE = re.compile(r"\b\d+-\d+-\d+\b")  # e.g. "1-0-1"
# Standalone dosing-frequency abbreviations (no leading number), e.g. "OD".
_FREQ_WORD_RE = re.compile(
    r"\b(od|bd|tds|qid|qds|prn|hs|sos|stat|nocte|mane|"
    r"once|twice|thrice|daily|weekly|nightly)\b",
    re.IGNORECASE,
)
_PUNCT_RE = re.compile(r"[^a-z0-9\s-]")


@lru_cache(maxsize=1)
def _dataset() -> dict:
    with _DATA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dataset_meta() -> dict:
    """Return the bundled dataset's metadata block (source label, version)."""
    return dict(_dataset().get("_meta", {}))


def _source_label() -> str:
    return _dataset().get("_meta", {}).get("source_label", "bundled interaction reference")


def normalize_drug(name: str | None) -> str:
    """Loosely normalize a medication label for matching.

    Lower-cases, strips dose/frequency/route noise and punctuation. Keeps the
    core drug words so ``"Amoxicillin 500mg 1-0-1"`` -> ``"amoxicillin"``.
    """
    if not name:
        return ""
    text = name.lower()
    text = _FREQ_RE.sub(" ", text)
    text = _DOSE_RE.sub(" ", text)
    text = _FREQ_WORD_RE.sub(" ", text)
    text = _PUNCT_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _canonicals_for(norm_name: str) -> set[str]:
    """Canonical drug/class keys whose aliases appear in ``norm_name``."""
    hits: set[str] = set()
    if not norm_name:
        return hits
    for canon, aliases in _dataset()["drug_aliases"].items():
        for alias in aliases:
            if alias.strip() in norm_name:
                hits.add(canon)
                break
    return hits


def extract_medication_names(context: list[dict]) -> list[str]:
    """Pull medication labels out of the RAG context / clinical facts list."""
    names: list[str] = []
    for fact in context or []:
        if str(fact.get("kind")) == "medication":
            label = fact.get("label")
            if label:
                names.append(str(label))
    return names


def extract_allergy_names(context: list[dict]) -> list[str]:
    """Pull allergy labels out of the RAG context / clinical facts list."""
    names: list[str] = []
    for fact in context or []:
        if str(fact.get("kind")) == "allergy":
            label = fact.get("label")
            if label:
                names.append(str(label))
    return names


def check_interactions(med_names: list[str]) -> list[dict]:
    """Return drug-drug interactions among ``med_names`` from the dataset.

    Each result: ``{drug_a, drug_b, severity, description, source}``. Only pairs
    satisfied by two *distinct* medications are reported; duplicates collapsed.
    """
    # canonical key -> list of original med labels that map to it
    present: dict[str, list[str]] = {}
    for original in med_names:
        norm = normalize_drug(original)
        for canon in _canonicals_for(norm):
            present.setdefault(canon, []).append(original)

    results: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for entry in _dataset()["interactions"]:
        a, b = entry["a"], entry["b"]
        if a not in present or b not in present:
            continue
        chosen = _distinct_pair(present[a], present[b])
        if chosen is None:
            continue
        key = tuple(sorted(chosen))
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "drug_a": chosen[0],
                "drug_b": chosen[1],
                "severity": entry["severity"],
                "description": entry["description"],
                "source": _source_label(),
            }
        )
    # Most serious first for a stable, useful ordering.
    order = {"contraindicated": 0, "major": 1, "moderate": 2, "minor": 3}
    results.sort(key=lambda r: order.get(r["severity"], 9))
    return results


def _distinct_pair(
    meds_a: list[str], meds_b: list[str]
) -> tuple[str, str] | None:
    """Pick two different medication labels, one matching each canonical key."""
    for ma in meds_a:
        for mb in meds_b:
            if ma != mb:
                return (ma, mb)
    return None


def check_allergy_conflicts(
    med_names: list[str], allergy_names: list[str]
) -> list[dict]:
    """Return medication-vs-allergy conflicts from the bundled class map.

    Each result: ``{medication, allergen, note, source}``.
    """
    classes = _dataset()["allergy_classes"]
    results: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for allergy in allergy_names:
        allergy_norm = normalize_drug(allergy)
        if not allergy_norm:
            continue
        for class_name, spec in classes.items():
            allergen_aliases = spec.get("allergen", [])
            if not any(a in allergy_norm for a in allergen_aliases):
                continue
            members = spec.get("members", [])
            for med in med_names:
                med_norm = normalize_drug(med)
                if not med_norm:
                    continue
                if any(m in med_norm for m in members):
                    key = (med, allergy)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(
                        {
                            "medication": med,
                            "allergen": allergy,
                            "note": (
                                f"{med} belongs to the {class_name}-class, which "
                                f"conflicts with the recorded {allergy} allergy — verify."
                            ),
                            "source": _source_label(),
                        }
                    )
    return results
