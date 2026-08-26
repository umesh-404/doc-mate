"""Summary quality evaluation routes.

Exposes the deterministic benchmark computed by :mod:`app.eval` — faithfulness
(hallucination), completeness (omission) and conciseness for generated patient
snapshots. Scores are reproducible offline (no LLM/provider call), so the same
numbers come out in stub mode and in provider mode.

Mount with::

    from app.api import evaluation
    app.include_router(evaluation.router)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Patient
from app.db.session import get_db
from app.eval.runner import (
    aggregate,
    evaluate_all,
    evaluate_patient,
    latest_evaluation,
    latest_summary,
)
from app.schemas.evaluation import (
    BenchmarkMeans,
    BenchmarkRead,
    BenchmarkRow,
    EvalRead,
)

router = APIRouter(tags=["evaluation"])


@router.post(
    "/patients/{patient_id}/summary/evaluate",
    response_model=EvalRead,
    dependencies=[Depends(get_current_user)],
)
def evaluate_latest_summary(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> EvalRead:
    """Score the patient's latest summary now and persist the result."""
    if db.get(Patient, patient_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    row = evaluate_patient(db, patient_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summary to evaluate for this patient",
        )
    return EvalRead.model_validate(row)


@router.get(
    "/patients/{patient_id}/summary/evaluation",
    response_model=EvalRead,
    dependencies=[Depends(get_current_user)],
)
def get_latest_evaluation(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> EvalRead:
    """Return the latest stored evaluation of the patient's latest summary."""
    summary = latest_summary(db, patient_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No summary yet"
        )
    row = latest_evaluation(db, summary.id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No evaluation yet"
        )
    return EvalRead.model_validate(row)


@router.get(
    "/evaluation/benchmark",
    response_model=BenchmarkRead,
    dependencies=[Depends(get_current_user)],
)
def get_benchmark(db: Annotated[Session, Depends(get_db)]) -> BenchmarkRead:
    """Run the benchmark sweep across every patient's latest summary."""
    results = evaluate_all(db)
    agg = aggregate(results)
    return BenchmarkRead(
        generated_at=datetime.now(timezone.utc),
        summary_count=agg["summary_count"],
        means=BenchmarkMeans(**agg["means"]),
        method=agg["method"],
        per_patient=[
            BenchmarkRow(
                patient_id=r["patient_id"],
                patient_name=r["patient_name"],
                faithfulness=r["eval"].faithfulness,
                completeness=r["eval"].completeness,
                conciseness=r["eval"].conciseness,
                overall=r["eval"].overall,
            )
            for r in results
        ],
    )
