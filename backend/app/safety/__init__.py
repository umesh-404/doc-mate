"""Clinical safety layer for Doc-mate.

Adds three *surfacing-only* safety capabilities on top of the RAG summary
(PROJECT.md section 4 — the AI never diagnoses or treats, it flags and cites):

* :mod:`app.safety.grounding` — a deterministic faithfulness/grounding check
  that scores how well each generated summary line is supported by its cited
  source. No LLM needed, so it runs identically in stub mode.
* :mod:`app.safety.interactions` — an offline drug-drug interaction and
  drug-allergy checker backed by a small bundled reference dataset. No network,
  no PHI leaves the system.
* :mod:`app.safety.alerts` — assembles neutral, citation-backed *flags*
  (allergies, interactions, out-of-range labs, missing data). Never phrased as
  a diagnosis or a treatment recommendation.
"""

from __future__ import annotations

from app.safety.alerts import build_alerts
from app.safety.grounding import GROUNDING_METHOD, check_grounding
from app.safety.interactions import (
    check_allergy_conflicts,
    check_interactions,
    extract_medication_names,
    normalize_drug,
)

__all__ = [
    "build_alerts",
    "check_grounding",
    "GROUNDING_METHOD",
    "check_interactions",
    "check_allergy_conflicts",
    "extract_medication_names",
    "normalize_drug",
]
