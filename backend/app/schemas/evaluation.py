"""Schemas for the summary quality evaluation harness (app.eval).

Contract::

    EvalRead  = {id, summary_id, faithfulness, completeness, conciseness,
                 overall, method, details, created_at}
    Benchmark = {generated_at, summary_count, means, method, per_patient:[...]}
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvalRead(BaseModel):
    """One persisted evaluation of one generated summary."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    summary_id: uuid.UUID
    faithfulness: float | None = None
    completeness: float | None = None
    conciseness: float | None = None
    overall: float | None = None
    method: str | None = None
    # Per-axis explanation: supported/unsupported items, missed facts, counts.
    details: dict | None = None
    created_at: datetime


class BenchmarkMeans(BaseModel):
    faithfulness: float | None = None
    completeness: float | None = None
    conciseness: float | None = None
    overall: float | None = None


class BenchmarkRow(BaseModel):
    patient_id: uuid.UUID
    patient_name: str
    faithfulness: float | None = None
    completeness: float | None = None
    conciseness: float | None = None
    overall: float | None = None


class BenchmarkRead(BaseModel):
    generated_at: datetime
    summary_count: int
    means: BenchmarkMeans
    method: str
    per_patient: list[BenchmarkRow] = []
