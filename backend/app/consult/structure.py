"""Deterministic structuring of a consultation transcript into a draft note.

Pure functions only — no database, no network, no provider SDK — so the whole
scribe runs offline and is unit-testable without Postgres.

Design rules that fall straight out of PROJECT.md section 4:

* **No assessment / diagnosis section exists.** The keys are exactly
  ``subjective | objective | plan | follow_up | flags``. The note records what
  was *said*, including the plan *as discussed by the doctor* — it never states
  a clinical conclusion of its own.
* **Nothing is invented.** Every line of the note is a sentence lifted from the
  transcript. Every proposed clinical item is a verbatim span of the transcript
  (matched by regex), so a dose string like ``"Metformin 500mg"`` reaches the
  doctor byte-for-byte. If the transcript does not mention a drug, a vital, or a
  condition, none is proposed.
* **Uncertainty is marked, never smoothed over.** Hedged or inaudible speech is
  flagged ``needs_verification`` and echoed under ``flags`` with the
  ``⚠ needs verification`` marker.
* Every proposed clinical item is ``needs_verification=True``: the doctor is the
  gate, always.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Section vocabulary — deliberately assessment-free.
# ---------------------------------------------------------------------------
SECTION_TITLES: dict[str, str] = {
    "subjective": "Subjective — what the patient described",
    "objective": "Objective — what was measured or examined",
    "plan": "Plan as discussed",
    "follow_up": "Follow-up",
    "flags": "⚠ Flags & things to verify",
}

SECTION_KEYS: tuple[str, ...] = (
    "subjective",
    "objective",
    "plan",
    "follow_up",
    "flags",
)

# Keys that must never appear — guarded by a test as well as by construction.
FORBIDDEN_SECTION_KEYS: frozenset[str] = frozenset(
    {"assessment", "diagnosis", "impression", "conclusion", "differential"}
)

_VERIFY_MARK = "⚠ needs verification"

# ---------------------------------------------------------------------------
# Cue lexicons. Order of evaluation is follow_up -> plan -> objective ->
# subjective, because a follow-up instruction usually also carries plan verbs.
# ---------------------------------------------------------------------------
_FOLLOW_UP_CUES = (
    "follow up",
    "follow-up",
    "review in",
    "review after",
    "come back",
    "come again",
    "next visit",
    "revisit",
    "see me in",
    "see you in",
    "return in",
    "recheck in",
    "repeat after",
)

_PLAN_CUES = (
    "start",
    "starting",
    "continue",
    "continuing",
    "stop",
    "discontinue",
    "prescrib",
    "advise",
    "advised",
    "advising",
    "increase",
    "decrease",
    "reduce",
    "we will",
    "we'll",
    "i will",
    "i'll",
    "let us",
    "let's",
    "recommend",
    "refer",
    "referral",
    "get a",
    "get an",
    "order",
    "repeat the",
    "take ",
    "twice a day",
    "once a day",
    "once daily",
    "after food",
    "before food",
    "at bedtime",
)

_OBJECTIVE_CUES = (
    "on examination",
    "examination",
    "examined",
    "vitals",
    "bp ",
    "bp is",
    "blood pressure",
    "pulse",
    "heart rate",
    "temperature",
    "temp is",
    "spo2",
    "saturation",
    "weight",
    "height",
    "hba1c",
    "glucose",
    "hemoglobin",
    "haemoglobin",
    "creatinine",
    "report shows",
    "reports show",
    "lab shows",
    "auscultation",
    "chest is",
    "abdomen is",
    "no murmur",
    "reading",
)

# Hedging / audio-quality markers -> the line is uncertain, flag it.
_HEDGE_CUES = (
    "maybe",
    "may be",
    "not sure",
    "unsure",
    "unclear",
    "possibly",
    "probably",
    "approximately",
    "roughly",
    "around ",
    "about ",
    "i think",
    "sounds like",
    "seems",
    "might",
    "inaudible",
    "unintelligible",
    "couldn't hear",
    "could not hear",
    "didn't catch",
    "?",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|[\r\n]+")


def _sentences(transcript: str) -> list[str]:
    """Split a transcript into trimmed, non-empty sentences."""
    parts = _SENTENCE_SPLIT.split(transcript or "")
    return [p.strip() for p in parts if p and p.strip()]


def _is_uncertain(sentence: str) -> bool:
    low = sentence.lower()
    return any(cue in low for cue in _HEDGE_CUES)


def _classify(sentence: str) -> str:
    """Route a sentence to a section key. Defaults to ``subjective``."""
    low = sentence.lower()
    if any(cue in low for cue in _FOLLOW_UP_CUES):
        return "follow_up"
    if any(cue in low for cue in _PLAN_CUES):
        return "plan"
    if any(cue in low for cue in _OBJECTIVE_CUES):
        return "objective"
    return "subjective"


# ---------------------------------------------------------------------------
# Verbatim clinical-item extraction.
#
# Every pattern captures a span of the transcript. Nothing is normalized,
# expanded, or unit-converted — what the doctor sees is what was said.
# ---------------------------------------------------------------------------

# "Metformin 500mg", "Amlodipine 5 mg", "Salbutamol 100mcg". Single drug token
# only, so a preceding verb ("continue Metformin 500mg") is never swallowed.
_MED_RE = re.compile(
    r"\b(?P<name>[A-Za-z][A-Za-z\-]{2,})\s*\d+(?:\.\d+)?\s*"
    r"(?:mg|mcg|g|ml|iu|units?|tablets?|tabs?)\b(?!\s*/)",
    re.IGNORECASE,
)

# Words that look like a drug to the pattern above but are lab/vital names
# ("hemoglobin 11.2 g/dL"). A hit here is never proposed as a medication.
_NOT_A_DRUG = frozenset(
    {
        "hemoglobin",
        "haemoglobin",
        "glucose",
        "sugar",
        "creatinine",
        "hba1c",
        "tsh",
        "ldl",
        "cholesterol",
        "temperature",
        "temp",
        "pulse",
        "weight",
        "height",
        "saturation",
        "spo2",
        "urea",
        "sodium",
        "potassium",
    }
)

# Dose schedules, captured only when literally present after the drug name.
_FREQ_RE = re.compile(
    r"\b(\d-\d-\d|once daily|once a day|twice a day|twice daily|"
    r"three times a day|thrice daily|at night|at bedtime|in the morning|"
    r"od|bd|tds|qid|prn|sos)\b",
    re.IGNORECASE,
)

_BP_RE = re.compile(
    r"\b(?:bp|blood pressure)\b[^0-9]{0,15}(\d{2,3}\s*/\s*\d{2,3})",
    re.IGNORECASE,
)
_PULSE_RE = re.compile(
    r"\b(?:pulse|heart rate)\b[^0-9]{0,15}(\d{2,3})", re.IGNORECASE
)
_TEMP_RE = re.compile(
    r"\b(?:temperature|temp|fever of)\b[^0-9]{0,15}(\d{2,3}(?:\.\d)?)\s*"
    r"(?:degrees\s*)?(?:°\s*)?([CF])?\b",
    re.IGNORECASE,
)
_SPO2_RE = re.compile(
    r"\b(?:spo2|sp02|oxygen saturation|saturation)\b[^0-9]{0,15}(\d{2,3})\s*(%)?",
    re.IGNORECASE,
)

# Named labs. The unit is captured ONLY if the speaker said it.
_LAB_NAMES = (
    "hba1c",
    "fasting glucose",
    "random glucose",
    "blood sugar",
    "glucose",
    "hemoglobin",
    "haemoglobin",
    "creatinine",
    "tsh",
    "ldl",
)
_LAB_UNIT = r"(%|mg/dl|g/dl|mmol/l|miu/l)"

_CONDITION_TERMS = (
    "type 2 diabetes mellitus",
    "type 1 diabetes mellitus",
    "type 2 diabetes",
    "type 1 diabetes",
    "diabetes",
    "essential hypertension",
    "hypertension",
    "high blood pressure",
    "bronchial asthma",
    "asthma",
    "hypothyroidism",
    "hyperthyroidism",
    "tuberculosis",
    "copd",
    "migraine",
    "anaemia",
    "anemia",
    "chronic kidney disease",
)

_ALLERGY_RE = re.compile(
    r"\baller(?:gic to|gy to)\s+([A-Za-z][A-Za-z\- ]{2,40}?)(?=[,.;]|\band\b|$)",
    re.IGNORECASE,
)


def _round_conf(value: float | None) -> float | None:
    return None if value is None else round(max(0.0, min(1.0, value)), 2)


def propose_items(transcript: str, confidence: float | None = 0.6) -> list[dict]:
    """Extract candidate clinical items **verbatim** from a transcript.

    Returns a list of ``{kind, label, value, unit, confidence,
    needs_verification}`` in order of first appearance in the transcript. Every
    item is ``needs_verification=True``: these are *proposals* for the doctor to
    accept, never facts. An empty transcript, or one with no drug/vital/
    condition actually spoken, yields ``[]`` — the scribe never invents one.

    The function is deterministic, so the same transcript always yields the same
    list in the same order; the API's ``item_indexes`` are indexes into it.
    """
    text = transcript or ""
    conf = _round_conf(confidence)
    found: list[tuple[int, dict]] = []
    seen: set[tuple[str, str]] = set()

    def _add(pos: int, kind: str, label: str, value=None, unit=None) -> None:
        label = label.strip()
        if not label:
            return
        key = (kind, label.lower())
        if key in seen:
            return
        seen.add(key)
        found.append(
            (
                pos,
                {
                    "kind": kind,
                    "label": label,
                    "value": value.strip() if isinstance(value, str) else value,
                    "unit": unit.strip() if isinstance(unit, str) else unit,
                    "confidence": conf,
                    # The doctor is the gate — always.
                    "needs_verification": True,
                },
            )
        )

    # Medications, with the dose string kept exactly as spoken.
    for match in _MED_RE.finditer(text):
        if match.group("name").lower() in _NOT_A_DRUG:
            continue
        label = match.group(0)
        # Look a short way past the drug for a spoken schedule ("1-0-1").
        tail = text[match.end() : match.end() + 60]
        freq = _FREQ_RE.search(tail)
        _add(match.start(), "medication", label, freq.group(1) if freq else None)

    # Vitals.
    for match in _BP_RE.finditer(text):
        _add(match.start(), "observation", "Blood pressure", match.group(1), "mmHg")
    for match in _PULSE_RE.finditer(text):
        _add(match.start(), "observation", "Pulse", match.group(1), "bpm")
    for match in _TEMP_RE.finditer(text):
        unit = match.group(2)
        _add(
            match.start(),
            "observation",
            "Temperature",
            match.group(1),
            f"°{unit.upper()}" if unit else None,
        )
    for match in _SPO2_RE.finditer(text):
        _add(match.start(), "observation", "SpO2", match.group(1), match.group(2))

    # Named labs — unit only when actually spoken.
    for name in _LAB_NAMES:
        pattern = re.compile(
            rf"\b{re.escape(name)}\b[^0-9]{{0,20}}(\d+(?:\.\d+)?)\s*{_LAB_UNIT}?",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            _add(
                match.start(),
                "observation",
                match.group(0)[: len(name)],
                match.group(1),
                match.group(2),
            )

    # Conditions — only surface terms literally spoken; longest form wins.
    lowered = text.lower()
    claimed: list[tuple[int, int]] = []
    for term in _CONDITION_TERMS:
        start = lowered.find(term)
        while start != -1:
            end = start + len(term)
            if not any(s <= start < e for s, e in claimed):
                claimed.append((start, end))
                _add(start, "condition", text[start:end])
            start = lowered.find(term, end)

    # Allergies.
    for match in _ALLERGY_RE.finditer(text):
        _add(match.start(), "allergy", match.group(1))

    found.sort(key=lambda pair: pair[0])
    return [item for _, item in found]


# ---------------------------------------------------------------------------
# Note assembly
# ---------------------------------------------------------------------------
def _empty_sections() -> dict[str, list[dict]]:
    return {key: [] for key in SECTION_KEYS}


def _sections_list(buckets: dict[str, list[dict]]) -> list[dict]:
    return [
        {"key": key, "title": SECTION_TITLES[key], "items": buckets[key]}
        for key in SECTION_KEYS
    ]


def structure_note(
    transcript: str,
    language: str = "en",
    use_llm: bool = False,
    stub_transcript: bool = False,
    confidence: float | None = 0.6,
) -> dict:
    """Turn a transcript into a draft note payload.

    Returns ``{"sections": [...], "proposed_items": [...], "meta": {...}}``
    where ``sections`` is the five-key list described in this module's docstring
    and ``proposed_items`` are verbatim candidates awaiting doctor verification.

    ``use_llm=True`` additionally routes the transcript through
    :mod:`app.llm` (the only place providers are ever called) to catch clinical
    items the regexes miss. Every LLM-returned item is **grounded**: its label
    must appear literally in the transcript or it is dropped, so the real-mode
    path cannot fabricate either. Any provider failure degrades silently to the
    deterministic draft plus a flag — never an exception, never a silent gap.
    """
    buckets = _empty_sections()
    sentences = _sentences(transcript)

    uncertain: list[str] = []
    for sentence in sentences:
        needs = _is_uncertain(sentence)
        buckets[_classify(sentence)].append(
            {"text": sentence, "needs_verification": needs}
        )
        if needs:
            uncertain.append(sentence)

    # --- flags: faithful status reporting, never a confident empty note ----
    if not sentences:
        buckets["flags"].append(
            {
                "text": (
                    "No consultation content was captured — nothing to draft."
                ),
                "needs_verification": True,
            }
        )
    for sentence in uncertain:
        buckets["flags"].append(
            {"text": f"{_VERIFY_MARK}: {sentence}", "needs_verification": True}
        )
    if stub_transcript:
        buckets["flags"].append(
            {
                "text": (
                    "Transcript came from the offline demo fallback, not a "
                    "speech model — treat every line as unconfirmed."
                ),
                "needs_verification": True,
            }
        )

    items = propose_items(transcript, confidence=confidence)

    meta: dict = {
        "language": language,
        "mode": "llm" if use_llm else "deterministic",
        "sentence_count": len(sentences),
        "uncertain_count": len(uncertain),
    }

    if use_llm:
        extra, note = _llm_items(transcript, items)
        if extra:
            items = items + extra
            meta["llm_items"] = len(extra)
        if note:
            meta["llm_error"] = note
            buckets["flags"].append(
                {
                    "text": (
                        "AI structuring was unavailable; this draft was built "
                        "by the offline rule-based scribe only."
                    ),
                    "needs_verification": True,
                }
            )

    buckets["flags"].append(
        {
            "text": (
                "Draft only — the system records what was said and never states "
                "a diagnosis. Review and edit every line before verifying."
            ),
            "needs_verification": True,
        }
    )

    return {
        "sections": _sections_list(buckets),
        "proposed_items": items,
        "meta": meta,
    }


def _llm_items(transcript: str, existing: list[dict]) -> tuple[list[dict], str | None]:
    """Ask the LLM layer for extra clinical candidates, grounded and de-duped.

    Returns ``(items, error_note)``. ``error_note`` carries only an exception
    *type* name — never transcript content — so it is safe to persist.
    """
    try:
        from app.llm import service as llm

        result = llm.extract_document(
            transcript.encode("utf-8"), "text/plain", "typed_note"
        )
    except Exception as exc:  # noqa: BLE001 — degrade, never break the note
        return [], type(exc).__name__

    lowered = (transcript or "").lower()
    seen = {(it["kind"], it["label"].lower()) for it in existing}
    extra: list[dict] = []
    for raw in result.get("items") or []:
        label = str(raw.get("label") or "").strip()
        kind = str(raw.get("kind") or "").strip().lower()
        if not label or not kind:
            continue
        # Grounding guard: if it was not said, it does not exist.
        if label.lower() not in lowered:
            continue
        key = (kind, label.lower())
        if key in seen:
            continue
        seen.add(key)
        extra.append(
            {
                "kind": kind,
                "label": label,
                "value": raw.get("value"),
                "unit": raw.get("unit"),
                "confidence": _round_conf(raw.get("confidence")),
                "needs_verification": True,
            }
        )
    return extra, None
