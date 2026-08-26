"""Offline medical-coding package (ICD-11 / NAMASTE) for Doc-mate.

Public API re-exported for convenience:
    from app.coding import Code, map_condition, search, coverage
"""

from __future__ import annotations

from app.coding.service import (
    SYSTEM_ICD11,
    SYSTEM_NAMASTE,
    SYSTEM_URI,
    Code,
    coverage,
    map_condition,
    primary_code,
    search,
)

__all__ = [
    "Code",
    "SYSTEM_ICD11",
    "SYSTEM_NAMASTE",
    "SYSTEM_URI",
    "map_condition",
    "primary_code",
    "search",
    "coverage",
]
