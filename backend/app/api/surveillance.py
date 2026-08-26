"""Anonymized public-health surveillance routes.

Aggregate epidemiological views over the whole record set — the scalability
story for Doc-mate: what one hospital's data does for one doctor, thousands of
hospitals' aggregated data can do for outbreak detection (cf. India's IDSP).

These endpoints return **aggregate counts only**. No patient id, name, ABHA id,
document id, encounter id or free-text clinical content is ever emitted; counts
below the documented K threshold are suppressed and ages are reported as bands.
The guarantees are implemented and documented in
:mod:`app.surveillance.aggregate`.

The outbreak signal is a naive statistical trip-wire for demo purposes — not a
validated epidemiological model and not a clinical or public-health conclusion.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.surveillance import (
    SurveillanceOverview,
    SurveillanceSignals,
    SurveillanceTrend,
)
from app.surveillance import aggregate

router = APIRouter(
    prefix="/surveillance",
    tags=["surveillance"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/overview", response_model=SurveillanceOverview)
def get_overview(db: Annotated[Session, Depends(get_db)]) -> dict:
    """Condition prevalence, age/sex bands, languages and data quality.

    All buckets are k-anonymised (K=5) and ages appear only as bands.
    """
    return aggregate.overview(db)


@router.get("/trends", response_model=SurveillanceTrend)
def get_trends(
    db: Annotated[Session, Depends(get_db)],
    condition: Annotated[
        str,
        Query(description="Condition label or ICD-11 / NAMASTE code."),
    ],
    bucket: Annotated[str, Query(pattern="^(week|month)$")] = "week",
) -> dict:
    """Counts per week/month for one condition, so a rising trend is visible.

    The query string is normalized through the offline coder and is never
    echoed back verbatim — the response reports the coded display label only.
    """
    return aggregate.time_series(db, condition=condition, bucket=bucket)


@router.get("/signals", response_model=SurveillanceSignals)
def get_signals(
    db: Annotated[Session, Depends(get_db)],
    bucket: Annotated[str, Query(pattern="^(week|month)$")] = "week",
) -> dict:
    """Run the documented naive outbreak trip-wire over aggregated counts.

    Demo-grade statistical signal only; it flags nothing below the K threshold
    and always requires human epidemiological review.
    """
    return aggregate.outbreak_signals(db, bucket=bucket)
