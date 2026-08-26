"""Tests for consent management + the access audit trail.

Runs against an in-memory SQLite database holding only the four tables the
governance layer touches (users, patients, consents, audit_logs). Postgres
column types are mapped to SQLite equivalents below — no live Postgres, no
network, no LLM.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    AuditAction,
    AuditLog,
    Consent,
    ConsentScope,
    ConsentStatus,
    Patient,
    User,
    UserRole,
)
from app.governance import (
    get_active_consent,
    grant_consent,
    record_access,
    require_consent,
    revoke_consent,
)
from app.governance.audit import (
    get_patient_access_history,
    get_recent_access,
    normalize_reason,
)
from app.governance.consent import (
    REASON_ALLOWED,
    REASON_BREAK_GLASS,
    REASON_EXPIRED,
    REASON_NO_CONSENT,
    REASON_REVOKED,
    REASON_SCOPE,
    scope_satisfies,
)


@compiles(JSONB, "sqlite")
def _jsonb_as_json(type_, compiler, **kw):  # pragma: no cover - DDL shim
    return "JSON"


TABLES = [
    Base.metadata.tables[name]
    for name in ("users", "patients", "consents", "audit_logs")
]


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def actor(db):
    user = User(
        email="doctor@example.test",
        full_name="Dr Demo",
        hashed_password="x",
        role=UserRole.doctor,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def patient(db):
    p = Patient(full_name="Demo Patient", preferred_language="en")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# Consent lifecycle
# ---------------------------------------------------------------------------
def test_grant_makes_consent_active_and_allowed(db, patient, actor) -> None:
    consent = grant_consent(
        db, patient.id, scope=ConsentScope.full_record, granted_by=actor
    )
    assert consent.status == ConsentStatus.granted
    assert get_active_consent(db, patient.id).id == consent.id

    decision = require_consent(db, patient.id, ConsentScope.summary_only)
    assert decision.allowed is True
    assert decision.reason == REASON_ALLOWED
    assert decision.consent_id == consent.id
    assert decision.break_glass is False


def test_no_consent_is_not_allowed(db, patient) -> None:
    decision = require_consent(db, patient.id, ConsentScope.full_record)
    assert decision.allowed is False
    assert decision.reason == REASON_NO_CONSENT
    assert decision.consent_id is None


def test_revoke_blocks_access_in_real_time(db, patient, actor) -> None:
    grant_consent(db, patient.id, granted_by=actor)
    revoked = revoke_consent(db, patient.id, reason="patient_request", actor=actor)

    assert revoked.status == ConsentStatus.revoked
    assert revoked.revoked_at is not None
    assert get_active_consent(db, patient.id) is None

    decision = require_consent(db, patient.id, ConsentScope.full_record)
    assert decision.allowed is False
    assert decision.reason == REASON_REVOKED


def test_expired_consent_is_not_allowed(db, patient, actor) -> None:
    grant_consent(
        db,
        patient.id,
        granted_by=actor,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    assert get_active_consent(db, patient.id) is None

    decision = require_consent(db, patient.id, ConsentScope.full_record)
    assert decision.allowed is False
    assert decision.reason == REASON_EXPIRED
    # The stored row is transitioned so state matches reality.
    stored = db.query(Consent).filter(Consent.patient_id == patient.id).one()
    assert stored.status == ConsentStatus.expired


def test_scope_is_enforced(db, patient, actor) -> None:
    grant_consent(db, patient.id, scope=ConsentScope.summary_only, granted_by=actor)
    assert require_consent(db, patient.id, ConsentScope.summary_only).allowed is True

    denied = require_consent(db, patient.id, ConsentScope.documents_only)
    assert denied.allowed is False
    assert denied.reason == REASON_SCOPE


def test_scope_satisfies_matrix() -> None:
    assert scope_satisfies(ConsentScope.full_record, ConsentScope.documents_only)
    assert scope_satisfies(ConsentScope.summary_only, ConsentScope.summary_only)
    assert not scope_satisfies(ConsentScope.summary_only, ConsentScope.full_record)
    assert scope_satisfies(ConsentScope.summary_only, None)


def test_grant_supersedes_previous_consent(db, patient, actor) -> None:
    first = grant_consent(db, patient.id, scope=ConsentScope.summary_only, granted_by=actor)
    second = grant_consent(db, patient.id, scope=ConsentScope.full_record, granted_by=actor)

    db.refresh(first)
    assert first.status == ConsentStatus.revoked
    assert get_active_consent(db, patient.id).id == second.id


# ---------------------------------------------------------------------------
# Break-glass
# ---------------------------------------------------------------------------
def test_break_glass_requires_a_reason(db, patient, actor) -> None:
    without = require_consent(
        db, patient.id, ConsentScope.full_record, actor=actor, break_glass_reason=None
    )
    assert without.allowed is False
    blank = require_consent(
        db, patient.id, ConsentScope.full_record, actor=actor, break_glass_reason="   "
    )
    assert blank.allowed is False
    # No break-glass audit row was written for a denied attempt.
    assert not [
        e for e in get_patient_access_history(db, patient.id) if e.break_glass
    ]


def test_break_glass_allows_and_flags_audit_row(db, patient, actor) -> None:
    decision = require_consent(
        db,
        patient.id,
        ConsentScope.full_record,
        actor=actor,
        break_glass_reason="emergency_care",
    )
    assert decision.allowed is True
    assert decision.reason == REASON_BREAK_GLASS
    assert decision.break_glass is True

    rows = [e for e in get_patient_access_history(db, patient.id) if e.break_glass]
    assert len(rows) == 1
    assert rows[0].action == AuditAction.break_glass
    assert rows[0].break_glass is True
    assert rows[0].reason == "emergency_care"
    assert rows[0].actor_user_id == actor.id
    assert rows[0].actor_role == "doctor"


def test_break_glass_also_overrides_a_revoked_consent(db, patient, actor) -> None:
    grant_consent(db, patient.id, granted_by=actor)
    revoke_consent(db, patient.id, actor=actor)
    decision = require_consent(
        db,
        patient.id,
        ConsentScope.full_record,
        actor=actor,
        break_glass_reason="patient_unconscious",
    )
    assert decision.allowed is True and decision.break_glass is True


# ---------------------------------------------------------------------------
# Audit trail — the no-PHI guarantee
# ---------------------------------------------------------------------------
PHI_STRINGS = (
    "Demo Patient",
    "Amoxicillin 500mg",
    "HbA1c 7.8%",
    "9876543210",
)


def test_audit_row_persists_only_ids_and_enums(db, patient, actor) -> None:
    doc_id = uuid.uuid4()
    entry = record_access(
        db,
        actor=actor,
        action=AuditAction.view_document,
        resource_type="document",
        resource_id=doc_id,
        patient_id=patient.id,
    )
    assert entry is not None

    row = db.get(AuditLog, entry.id)
    assert row.actor_user_id == actor.id
    assert row.actor_role == "doctor"
    assert row.action == AuditAction.view_document
    assert row.resource_type == "document"
    assert row.resource_id == doc_id
    assert row.patient_id == patient.id
    assert row.reason is None

    # Every persisted column is an id, an enum, a bool, a timestamp, or a
    # coded label — nothing free-form.
    values = {c.name: getattr(row, c.name) for c in AuditLog.__table__.columns}
    for name, value in values.items():
        if isinstance(value, AuditAction):
            continue
        if isinstance(value, str):
            assert name in {"actor_role", "resource_type", "reason"}
            assert len(value) <= 64


def test_free_text_reason_is_never_stored_verbatim(db, patient, actor) -> None:
    for phi in PHI_STRINGS:
        record_access(
            db,
            actor=actor,
            action=AuditAction.view_patient,
            resource_type="patient",
            resource_id=patient.id,
            patient_id=patient.id,
            break_glass=True,
            reason=f"needed for {phi}",
        )

    rows = get_patient_access_history(db, patient.id)
    assert len(rows) == len(PHI_STRINGS)
    for row in rows:
        assert row.reason == "other"
        blob = " ".join(
            str(getattr(row, c.name)) for c in AuditLog.__table__.columns
        )
        for phi in PHI_STRINGS:
            assert phi not in blob


def test_normalize_reason_uses_a_closed_vocabulary() -> None:
    assert normalize_reason("Emergency Care") == "emergency_care"
    assert normalize_reason("emergency-care") == "emergency_care"
    assert normalize_reason("patient said her chest hurts") == "other"
    assert normalize_reason("") is None
    assert normalize_reason(None) is None


def test_consent_changes_are_themselves_audited(db, patient, actor) -> None:
    grant_consent(db, patient.id, granted_by=actor)
    revoke_consent(db, patient.id, reason="patient_request", actor=actor)

    actions = [e.action for e in get_patient_access_history(db, patient.id)]
    assert AuditAction.consent_grant in actions
    assert AuditAction.consent_revoke in actions


def test_record_access_never_raises_into_the_request_path(patient) -> None:
    class BrokenSession:
        def add(self, obj):
            raise RuntimeError("db is down")

        def rollback(self):
            raise RuntimeError("still down")

    assert (
        record_access(
            BrokenSession(),
            actor=None,
            action=AuditAction.view_patient,
            patient_id=patient.id,
        )
        is None
    )


def test_recent_access_is_capped_and_newest_first(db, patient, actor) -> None:
    for _ in range(5):
        record_access(
            db,
            actor=actor,
            action=AuditAction.view_patient,
            patient_id=patient.id,
        )
    rows = get_recent_access(db, limit=3)
    assert len(rows) == 3
    stamps = [r.created_at for r in rows]
    assert stamps == sorted(stamps, reverse=True)
