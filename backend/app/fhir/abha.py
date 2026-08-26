"""Mock ABHA identity resolver (demo only — NOT real NHA/ABDM integration).

Given an ABHA-style id, deterministically derives a plausible identity so the
demo can show an "ABHA lookup" step without any external call or real PII. Every
result is clearly flagged ``source="mock"`` and ``verified`` is a demo constant,
never an assertion about a real person.

Determinism: identical ``abha_id`` always yields the same mock identity (seeded
by a hash of the id), so the demo is reproducible.
"""

from __future__ import annotations

import hashlib

# Synthetic name pools (neutral, India-context demo data — not real people).
_FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kavya",
    "Rohan", "Meera", "Priya", "Arjun", "Saanvi", "Karthik", "Nisha",
    "Rahul", "Lakshmi",
]
_LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Patel", "Gupta",
    "Das", "Rao", "Menon", "Bose", "Khan", "Singh", "Pillai",
]
_GENDERS = ["male", "female", "other"]


def _digest(abha_id: str) -> bytes:
    return hashlib.sha256(abha_id.strip().encode("utf-8")).digest()


def mock_identity(abha_id: str) -> dict[str, object]:
    """Return a deterministic MOCK ABHA identity for ``abha_id``.

    Not a real lookup: derives name/gender/birth-year from a hash of the id.
    """
    d = _digest(abha_id)
    first = _FIRST_NAMES[d[0] % len(_FIRST_NAMES)]
    last = _LAST_NAMES[d[1] % len(_LAST_NAMES)]
    gender = _GENDERS[d[2] % len(_GENDERS)]
    # Birth year in a plausible adult range 1945..2007.
    year = 1945 + (d[3] % 63)
    return {
        "abha_id": abha_id,
        "name": f"{first} {last}",
        "gender": gender,
        "year_of_birth": year,
        "verified": True,
        "source": "mock",
    }
