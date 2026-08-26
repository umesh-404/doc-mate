"""Schemas for the anonymized public-health surveillance endpoints.

Every field here is an aggregate. There is deliberately no field capable of
carrying a patient id, name, ABHA id, document id or free-text clinical
content — see :mod:`app.surveillance.aggregate` for the guarantees.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SuppressibleCount(BaseModel):
    """A count that is ``None`` when the bucket falls below the K threshold."""

    count: int | None = None
    suppressed: bool = False


class ConditionCount(SuppressibleCount):
    """Prevalence of one normalized condition."""

    label: str
    code: str | None = None
    system: str | None = None


class AgeSexCell(SuppressibleCount):
    """One age-band x sex cell. Ages are bands only — never exact."""

    age_band: str
    sex: str


class AgeSexDistribution(BaseModel):
    condition: str
    code: str | None = None
    system: str | None = None
    buckets: list[AgeSexCell] = Field(default_factory=list)


class LanguageCount(SuppressibleCount):
    language: str


class StatusCount(BaseModel):
    status: str
    count: int


class DataQuality(BaseModel):
    by_status: list[StatusCount] = Field(default_factory=list)
    total_documents: int = 0
    failed_documents: int = 0
    note: str | None = None


class SurveillanceOverview(BaseModel):
    generated_at: str
    k_threshold: int
    suppression_rule: str
    privacy_note: str
    #: Suppressed (``None``) when the whole population is below K.
    patient_count: int | None = None
    conditions: list[ConditionCount] = Field(default_factory=list)
    age_sex: list[AgeSexDistribution] = Field(default_factory=list)
    languages: list[LanguageCount] = Field(default_factory=list)
    data_quality: DataQuality


class TrendPoint(SuppressibleCount):
    #: ISO date of the first day of the week/month bucket.
    period_start: str


class SurveillanceTrend(BaseModel):
    condition: str
    code: str | None = None
    system: str | None = None
    bucket: str
    k_threshold: int
    suppression_rule: str
    privacy_note: str
    points: list[TrendPoint] = Field(default_factory=list)


class OutbreakSignal(BaseModel):
    condition: str
    code: str | None = None
    system: str | None = None
    level: str  # "watch" | "alert"
    current: int
    baseline: float
    note: str


class SurveillanceSignals(BaseModel):
    generated_at: str
    bucket: str
    method: str
    k_threshold: int
    suppression_rule: str
    privacy_note: str
    signals: list[OutbreakSignal] = Field(default_factory=list)
