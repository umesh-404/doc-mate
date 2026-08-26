"""Anonymized public-health surveillance layer.

Aggregate-only epidemiological views over the hospital's records. See
:mod:`app.surveillance.aggregate` for the privacy guarantees this package
enforces (aggregate counts only, k-anonymity, age bands, coded labels only).
"""

from app.surveillance.aggregate import (
    AGE_BANDS,
    K_THRESHOLD,
    OUTBREAK_METHOD,
    PRIVACY_NOTE,
    SUPPRESSION_RULE,
    age_band,
    age_sex_distribution,
    condition_prevalence,
    data_quality,
    language_distribution,
    outbreak_signals,
    overview,
    time_series,
)

__all__ = [
    "AGE_BANDS",
    "K_THRESHOLD",
    "OUTBREAK_METHOD",
    "PRIVACY_NOTE",
    "SUPPRESSION_RULE",
    "age_band",
    "age_sex_distribution",
    "condition_prevalence",
    "data_quality",
    "language_distribution",
    "outbreak_signals",
    "overview",
    "time_series",
]
