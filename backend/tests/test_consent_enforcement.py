"""Tests for the route-level consent gate (``app.api._consent``).

A minimal FastAPI app is built around the real dependency so the gate's HTTP
behaviour is exercised end to end — status codes *and* the audit rows it writes
— without needing Postgres, object storage or an LLM. The database is an
in-memory SQLite holding only the tables governance touches.

The three modes under test:

* ``audit_only`` (the default) — never blocks, always records a denial.
* ``enforce``                  — 403 without consent; 200 with consent, and
                                 200 + a ``break_glass`` audit row when an
                                 explicit break-glass reason is supplied.
* ``off``                      — no check, no audit row.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.api._consent import DENIAL_REASON_CODE, consent_gate
from app.core.config import settings
from app.core.security import get_current_user
from app.db.base import Base
from app.db.models import (
    AuditAction,
    AuditLog,
    ConsentScope,
    Document,
    DocumentStatus,
    DocumentType,
    Patient,
    User,
    UserRole,
)
from app.db.session import get_db
from app.governance import grant_consent, revoke_consent


@compiles(JSONB, "sqlite")
def _jsonb_as_json(type_, compiler, **kw):  # pragma: no cover - DDL shim
    return "JSON"


TABLES = [
    Base.metadata.tables[name]
    for name in (
        "users",
        "patients",
        "encounters",
        "documents",
        "consents",
        "audit_logs",
    )
]


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def actor(db) -> User:
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
def patient(db) -> Patient:
    p = Patient(full_name="Demo Patient", preferred_language="en")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture()
def document(db, patient) -> Document:
    doc = Document(
        patient_id=patient.id,
        doc_type=DocumentType.prescription,
        status=DocumentStatus.extracted,
        filename="rx.png",
        storage_key="demo/rx.png",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@pytest.fixture()
def client(db, actor) -> TestClient:
    """A tiny app whose routes carry the real consent gate."""
    app = FastAPI()

    @app.get(
        "/p/{patient_id}",
        dependencies=[Depends(consent_gate(AuditAction.view_patient))],
    )
    def read_patient(patient_id: uuid.UUID) -> dict:
        return {"ok": True}

    @app.get(
        "/d/{document_id}",
        dependencies=[
            Depends(
                consent_gate(
                    AuditAction.view_document, document_param="document_id"
                )
            )
        ],
    )
    def read_document(document_id: uuid.UUID) -> dict:
        return {"ok": True}

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: actor
    return TestClient(app)


def _audit_rows(db) -> list[AuditLog]:
    return list(db.execute(select(AuditLog)).scalars().all())


def _mode(monkeypatch, value: str) -> None:
    monkeypatch.setattr(settings, "consent_enforcement", value)
    assert settings.consent_mode == value


# ---------------------------------------------------------------------------
# audit_only (the default) — never blocks the demo
# ---------------------------------------------------------------------------
def test_default_mode_is_audit_only() -> None:
    assert settings.consent_mode == "audit_only"


def test_audit_only_allows_access_without_consent(
    client, db, patient, monkeypatch
) -> None:
    _mode(monkeypatch, "audit_only")
    resp = client.get(f"/p/{patient.id}")
    assert resp.status_code == 200


def test_audit_only_records_the_denied_decision(
    client, db, patient, monkeypatch
) -> None:
    _mode(monkeypatch, "audit_only")
    client.get(f"/p/{patient.id}")

    rows = _audit_rows(db)
    assert len(rows) == 1
    (row,) = rows
    assert row.action == AuditAction.view_patient
    assert row.patient_id == patient.id
    # Coded reason only — the closed vocabulary keeps PHI out of the trail.
    assert row.reason == DENIAL_REASON_CODE
    assert row.break_glass is False


def test_audit_only_with_consent_writes_no_denial_row(
    client, db, patient, actor, monkeypatch
) -> None:
    _mode(monkeypatch, "audit_only")
    grant_consent(db, patient.id, scope=ConsentScope.full_record, granted_by=actor)
    before = len(_audit_rows(db))  # the consent_grant row itself

    assert client.get(f"/p/{patient.id}").status_code == 200
    assert len(_audit_rows(db)) == before


# ---------------------------------------------------------------------------
# enforce
# ---------------------------------------------------------------------------
def test_enforce_blocks_without_consent(client, db, patient, monkeypatch) -> None:
    _mode(monkeypatch, "enforce")
    resp = client.get(f"/p/{patient.id}")
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["error"] == "consent_required"
    assert detail["reason"] == "no_consent_on_record"


def test_enforce_audits_the_block(client, db, patient, monkeypatch) -> None:
    _mode(monkeypatch, "enforce")
    client.get(f"/p/{patient.id}")

    rows = _audit_rows(db)
    assert [r.reason for r in rows] == [DENIAL_REASON_CODE]
    assert rows[0].action == AuditAction.view_patient


def test_enforce_allows_with_active_consent(
    client, db, patient, actor, monkeypatch
) -> None:
    _mode(monkeypatch, "enforce")
    grant_consent(db, patient.id, scope=ConsentScope.full_record, granted_by=actor)
    assert client.get(f"/p/{patient.id}").status_code == 200


def test_enforce_blocks_again_after_consent_is_revoked(
    client, db, patient, actor, monkeypatch
) -> None:
    _mode(monkeypatch, "enforce")
    grant_consent(db, patient.id, scope=ConsentScope.full_record, granted_by=actor)
    assert client.get(f"/p/{patient.id}").status_code == 200

    revoke_consent(db, patient.id, actor=actor)
    resp = client.get(f"/p/{patient.id}")
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason"] == "consent_revoked"


def test_enforce_break_glass_allows_and_is_audit_flagged(
    client, db, patient, monkeypatch
) -> None:
    _mode(monkeypatch, "enforce")
    resp = client.get(f"/p/{patient.id}?break_glass_reason=emergency_care")
    assert resp.status_code == 200

    rows = _audit_rows(db)
    flagged = [r for r in rows if r.break_glass]
    assert len(flagged) == 1
    assert flagged[0].action == AuditAction.break_glass
    assert flagged[0].reason == "emergency_care"
    assert flagged[0].patient_id == patient.id


def test_break_glass_free_text_reason_is_coded_before_storage(
    client, db, patient, monkeypatch
) -> None:
    """A caller must not be able to push patient content into the audit trail."""
    _mode(monkeypatch, "enforce")
    resp = client.get(f"/p/{patient.id}?break_glass_reason=Ramesh has chest pain")
    assert resp.status_code == 200

    (flagged,) = [r for r in _audit_rows(db) if r.break_glass]
    assert flagged.reason == "other"


# ---------------------------------------------------------------------------
# off
# ---------------------------------------------------------------------------
def test_off_mode_skips_the_check_entirely(
    client, db, patient, monkeypatch
) -> None:
    _mode(monkeypatch, "off")
    assert client.get(f"/p/{patient.id}").status_code == 200
    assert _audit_rows(db) == []


def test_unknown_mode_fails_safe_to_audit_only(monkeypatch) -> None:
    monkeypatch.setattr(settings, "consent_enforcement", "ENFORCEE")
    assert settings.consent_mode == "audit_only"


# ---------------------------------------------------------------------------
# Patient resolution from a document path parameter
# ---------------------------------------------------------------------------
def test_document_route_resolves_the_patient_and_blocks(
    client, db, document, patient, monkeypatch
) -> None:
    _mode(monkeypatch, "enforce")
    resp = client.get(f"/d/{document.id}")
    assert resp.status_code == 403
    (row,) = _audit_rows(db)
    assert row.action == AuditAction.view_document
    assert row.patient_id == patient.id


def test_document_route_allows_with_consent(
    client, db, document, patient, actor, monkeypatch
) -> None:
    _mode(monkeypatch, "enforce")
    grant_consent(db, patient.id, scope=ConsentScope.full_record, granted_by=actor)
    assert client.get(f"/d/{document.id}").status_code == 200


def test_unknown_document_is_not_blocked_by_the_gate(
    client, db, monkeypatch
) -> None:
    """Nothing patient-scoped to check -> let the route return its own 404."""
    _mode(monkeypatch, "enforce")
    assert client.get(f"/d/{uuid.uuid4()}").status_code == 200
