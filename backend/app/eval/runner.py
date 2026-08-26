"""Compute + persist summary quality evaluations.

Scoring itself lives in :mod:`app.eval.metrics` (pure functions, no DB). This
module is the thin DB layer: pull a summary and the patient's facts, score
them, and write a :class:`~app.db.models.SummaryEval` row.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Patient, Summary, SummaryEval
from app.eval.metrics import EVAL_METHOD, score_summary
from app.rag.retrieval import gather_context

logger = logging.getLogger("docmate.eval")


def latest_summary(db: Session, patient_id: uuid.UUID) -> Summary | None:
    """Return the patient's most recently generated summary, if any."""
    stmt = (
        select(Summary)
        .where(Summary.patient_id == patient_id)
        .order_by(Summary.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def latest_evaluation(db: Session, summary_id: uuid.UUID) -> SummaryEval | None:
    """Return the most recent evaluation row for a summary, if any."""
    stmt = (
        select(SummaryEval)
        .where(SummaryEval.summary_id == summary_id)
        .order_by(SummaryEval.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def evaluate_summary(db: Session, summary_id: uuid.UUID) -> SummaryEval | None:
    """Score one summary and persist the result. None if the summary is gone."""
    summary = db.get(Summary, summary_id)
    if summary is None:
        logger.warning("evaluation skipped: summary id=%s not found", summary_id)
        return None

    context = gather_context(db, summary.patient_id)
    scores = score_summary(summary.sections or [], context)

    row = SummaryEval(
        summary_id=summary.id,
        faithfulness=scores["faithfulness"],
        completeness=scores["completeness"],
        conciseness=scores["conciseness"],
        overall=scores["overall"],
        method=EVAL_METHOD,
        details=scores["details"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        "evaluated summary id=%s faith=%.2f comp=%.2f conc=%.2f overall=%.2f",
        summary.id,
        scores["faithfulness"],
        scores["completeness"],
        scores["conciseness"],
        scores["overall"],
    )
    return row


def evaluate_patient(db: Session, patient_id: uuid.UUID) -> SummaryEval | None:
    """Evaluate a patient's latest summary. None when they have none yet."""
    summary = latest_summary(db, patient_id)
    if summary is None:
        return None
    return evaluate_summary(db, summary.id)


def evaluate_all(db: Session) -> list[dict]:
    """Benchmark sweep: evaluate every patient's latest summary.

    Returns one row per patient that has a summary::

        {"patient_id": UUID, "patient_name": str, "summary_id": UUID,
         "eval": SummaryEval}

    Patients without a summary are skipped (they have nothing to score).
    """
    patients = list(
        db.execute(select(Patient).order_by(Patient.created_at)).scalars().all()
    )
    results: list[dict] = []
    for patient in patients:
        summary = latest_summary(db, patient.id)
        if summary is None:
            continue
        row = evaluate_summary(db, summary.id)
        if row is None:
            continue
        results.append(
            {
                "patient_id": patient.id,
                "patient_name": patient.full_name,
                "summary_id": summary.id,
                "eval": row,
            }
        )
    return results


def aggregate(results: list[dict]) -> dict:
    """Mean of each axis across a sweep, plus omission/hallucination counts."""
    axes = ("faithfulness", "completeness", "conciseness", "overall")
    means = {a: None for a in axes}
    unsupported = 0
    missed = 0

    if results:
        for axis in axes:
            values = [
                getattr(r["eval"], axis)
                for r in results
                if getattr(r["eval"], axis) is not None
            ]
            means[axis] = round(sum(values) / len(values), 4) if values else None
        for r in results:
            details = r["eval"].details or {}
            unsupported += (details.get("faithfulness") or {}).get(
                "unsupported_count", 0
            )
            missed += (details.get("completeness") or {}).get("missed_count", 0)

    return {
        "summary_count": len(results),
        "means": means,
        "unsupported_item_count": unsupported,
        "missed_fact_count": missed,
        "method": EVAL_METHOD,
    }
