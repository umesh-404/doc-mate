"""Consent management + access audit trail (DPDP Act 2023 alignment).

Public API — import these four names anywhere in the backend:

``record_access(db, *, actor, action, ...)``
    Append one audit row. Ids/enums only, never patient content. Never raises.

``audited(action, *, resource_type=..., patient_param="patient_id")``
    FastAPI dependency factory. Drop into a route's ``dependencies=[...]`` to
    log the access with zero changes to the route body.

``require_consent(db, patient_id, scope, *, actor=None, break_glass_reason=None)``
    Returns a :class:`~app.governance.consent.ConsentDecision`
    ``{allowed, reason, consent_id, break_glass}``. Break-glass access is
    permitted only with an explicit reason and is always audit-flagged.

``get_active_consent(db, patient_id)``
    The patient's current granted, unexpired consent, or ``None``.
"""

from __future__ import annotations

from app.governance.audit import (
    ACCESS_REASONS,
    MAX_AUDIT_ROWS,
    audited,
    get_patient_access_history,
    get_recent_access,
    iter_audit_entries,
    normalize_reason,
    record_access,
)
from app.governance.consent import (
    ConsentDecision,
    get_active_consent,
    get_latest_consent,
    grant_consent,
    require_consent,
    revoke_consent,
    scope_satisfies,
)

__all__ = [
    # audit
    "record_access",
    "audited",
    "get_patient_access_history",
    "get_recent_access",
    "iter_audit_entries",
    "normalize_reason",
    "ACCESS_REASONS",
    "MAX_AUDIT_ROWS",
    # consent
    "require_consent",
    "get_active_consent",
    "get_latest_consent",
    "grant_consent",
    "revoke_consent",
    "scope_satisfies",
    "ConsentDecision",
]
