"""OPD triage + queue intelligence.

Government-hospital OPDs run 500-2000+ walk-in patients a day, and the queue is
ordered purely by arrival. Doc-mate already holds each patient's ingested
record, so it can propose a *review order* by clinical urgency instead.

Hard boundary (PROJECT.md section 4): nothing in this package diagnoses, and
nothing here decides anything. It produces a **suggested review priority** with
a transparent, cited, rule-based explanation that a triage nurse or doctor
confirms or overrides. No value is ever invented — every contributing factor is
derived from an already-ingested clinical item, safety flag, or document status,
and is cited to its source document wherever one exists.
"""

from app.triage.scoring import (
    TRIAGE_DISCLAIMER,
    TriageScore,
    score_patient,
)

__all__ = ["TRIAGE_DISCLAIMER", "TriageScore", "score_patient"]
