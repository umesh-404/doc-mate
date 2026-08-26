"""Seed a bulk synthetic *background cohort* for Doc-mate.

Run from the ``backend/`` directory, AFTER migrations::

    alembic upgrade head
    python -m scripts.seed_cohort          # default COHORT_SIZE patients
    python -m scripts.seed_cohort 250      # optional size override

This **complements** ``scripts.seed_demo`` — it does not replace it. The five
hand-crafted showcase patients (Rukmini, Arjun, Meena, Karthik, Lakshmi) live in
``scripts.seed_demo`` and are never touched, read, or duplicated here: cohort
patients are keyed by their own ABHA-style prefix (see :data:`ABHA_PREFIX`),
which is disjoint from the showcase ids.

Why this exists
---------------
Two features are *population* features and simply cannot be demonstrated on a
five-patient database:

1. **Public-health surveillance** (:mod:`app.surveillance.aggregate`) applies
   k-anonymity with K=5. With five patients every bucket falls below the
   threshold, so the whole dashboard renders suppressed and empty, and the
   outbreak trip-wire can never fire (it refuses to signal on a suppressible
   cell by design).
2. **OPD triage queue** (:mod:`app.triage.queue`). A real government OPD sees
   500-2000 patients a day; a five-row queue with no priority spread does not
   look like one.

This seeder therefore creates a realistic *background* population: enough
patients per condition to clear K, a six-month spread of dates, one deliberately
engineered seasonal spike, and a believable emergency / urgent / routine mix.

What it creates (per cohort patient)
------------------------------------
* A ``Patient`` with a clearly-synthetic Indian name (regions varied), age, sex,
  a cohort ABHA-style id, and a preferred language drawn from an uneven
  ``en``/``hi``/``ta`` mix.
* 1-2 ``Document`` rows — mostly ``verified``, some ``extracted``, a few
  ``failed`` with a plain reason, so the data-quality panel reports honest
  numbers rather than a suspiciously perfect 100%.
* 2-5 ``ClinicalItem`` rows, every one linked to a source document via
  ``source_document_id`` (citations stay load-bearing, PROJECT.md section 10).

Deliberately **not** created: Chunks/embeddings and Summaries. Cohort patients
are background population for the aggregate views, not snapshot showcases, and
skipping them keeps the seed fast. Opening a cohort patient in the doctor UI
will generate a summary on demand like any other patient.

Determinism and idempotency
---------------------------
``random`` is seeded with :data:`RANDOM_SEED`, so every run of a given size
produces byte-for-byte the same cohort — demos are reproducible and the
engineered outbreak lands on the same counts each time. Patients are keyed by
ABHA id, so re-running skips everything already present and never duplicates a
row. Re-run it as the "reset" step as often as you like.

Safety (PROJECT.md section 4)
-----------------------------
Every value here is fabricated; no real person, ABHA id, phone number or record
is represented. Condition labels are neutral record entries, never conclusions,
and out-of-range vitals/labs are just recorded numbers for a clinician to
verify — this file states no diagnosis and no treatment.
"""

from __future__ import annotations

import random
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from app.db.models import (
    ClinicalItem,
    ClinicalItemKind,
    Document,
    DocumentStatus,
    DocumentType,
    Patient,
)
from app.db.session import get_sessionmaker

TODAY = date.today()

#: Fixed seed — reproducible demos. Never replace this with a clock value.
RANDOM_SEED = 20260826

#: Default number of background patients.
COHORT_SIZE = 100

#: ABHA-style prefix reserved for the cohort. ``scripts.seed_demo`` uses
#: 11-/22-/33-/44-/55-, so this namespace can never collide with a showcase
#: patient — the reason re-running either seeder is safe.
ABHA_PREFIX = "90"

#: Commit every N patients so 100+ patients seed in one quick pass.
BATCH_SIZE = 20


def _days_ago(n: int) -> date:
    return TODAY - timedelta(days=n)


# ---------------------------------------------------------------------------
# Synthetic name pools (regions varied). Fabricated combinations only.
# ---------------------------------------------------------------------------
_GIVEN_NAMES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # region: (female given names, male given names)
    "north": (
        ("Sunita", "Kavita", "Rekha", "Poonam", "Anita", "Shalini", "Neha"),
        ("Rajesh", "Vikram", "Sandeep", "Manoj", "Ashok", "Deepak", "Ravi"),
    ),
    "south": (
        ("Latha", "Revathi", "Anitha", "Kalpana", "Sumathi", "Vasanthi"),
        ("Murugan", "Senthil", "Ramesh", "Balaji", "Prakash", "Ganesan"),
    ),
    "east": (
        ("Sharmila", "Moumita", "Sujata", "Ruma", "Papiya", "Anjali"),
        ("Subhash", "Tapan", "Debashish", "Amit", "Pranab", "Sanjib"),
    ),
    "west": (
        ("Manisha", "Pallavi", "Snehal", "Vaishali", "Jyoti", "Bhavna"),
        ("Mahesh", "Nilesh", "Sachin", "Rohit", "Kiran", "Pravin"),
    ),
}

_FAMILY_NAMES: dict[str, tuple[str, ...]] = {
    "north": ("Sharma", "Verma", "Yadav", "Chauhan", "Mishra", "Rathore"),
    "south": ("Raman", "Iyer", "Naidu", "Pillai", "Reddy", "Krishnan"),
    "east": ("Das", "Ghosh", "Sarkar", "Mondal", "Chakraborty", "Bose"),
    "west": ("Patil", "Deshmukh", "Joshi", "Shah", "Kulkarni", "Gaikwad"),
}

_REGIONS = tuple(_GIVEN_NAMES)

#: Uneven, plausible language mix for a north-Indian district hospital that
#: also serves migrant workers: mostly English-charted, a large Hindi share and
#: a smaller Tamil one.
_LANGUAGE_MIX: tuple[tuple[str, int], ...] = (("en", 55), ("hi", 30), ("ta", 15))


# ---------------------------------------------------------------------------
# Condition plan.
#
# Every label below was checked against app.coding.service and maps to a real
# bundled ICD-11 code, so surveillance reports the code system's own display
# text rather than pooling the cohort into "Unclassified":
#
#   Type 2 diabetes mellitus  -> 5A11  Type 2 diabetes mellitus
#   Essential hypertension    -> BA00  Essential hypertension
#   Iron deficiency anaemia   -> 3A00  Iron deficiency anaemia
#   Bronchial asthma          -> CA23  Asthma
#   Acute gastroenteritis     -> 1E32  Gastroenteritis
#   Pulmonary tuberculosis    -> 1B10  Tuberculosis
#   Dengue fever              -> 1D40  Dengue
#
# Counts are chosen so each bucket clears K=5 comfortably at the default size.
# ---------------------------------------------------------------------------
BASELINE_CONDITIONS: tuple[tuple[str, int], ...] = (
    ("Essential hypertension", 24),
    ("Type 2 diabetes mellitus", 22),
    ("Iron deficiency anaemia", 14),
    ("Acute gastroenteritis", 12),
    ("Bronchial asthma", 11),
    ("Pulmonary tuberculosis", 7),
)

#: The engineered outbreak. Dengue is seasonally plausible in India.
#: A handful of scattered baseline cases across the six-month window, then a
#: cluster inside the CURRENT week.
OUTBREAK_CONDITION = "Dengue fever"
OUTBREAK_BASELINE_COUNT = 3
OUTBREAK_BASELINE_WEEKS = (22, 16, 10)  # weeks ago, one case each
OUTBREAK_SPIKE_COUNT = 15

#: Baseline conditions are spread over these weeks-ago bounds. The window
#: deliberately stops short of the last few weeks so that no baseline condition
#: has >= K cases in its own most recent period — the outbreak rule then fires
#: for the dengue cluster and for nothing else.
BASELINE_WEEK_MIN = 4
BASELINE_WEEK_MAX = 26

#: Chronic conditions that justify a maintenance medication on the record.
_CHRONIC = {
    "Essential hypertension",
    "Type 2 diabetes mellitus",
    "Bronchial asthma",
}

_MEDICATION_FOR: dict[str, tuple[str, str]] = {
    "Essential hypertension": ("Amlodipine 5mg", "1-0-0"),
    "Type 2 diabetes mellitus": ("Metformin 500mg", "1-0-1"),
    "Bronchial asthma": ("Salbutamol inhaler", "PRN"),
}


# ---------------------------------------------------------------------------
# Observation profiles.
#
# Values are read straight against app.triage.scoring._RANGES so the queue shows
# a believable spread instead of 100 routine rows. "critical" profiles carry two
# or more markedly out-of-range values (the scorer's emergency floor), "severe"
# profiles carry exactly one (its urgent floor), "mild" profiles sit outside the
# typical range without being severe, and "normal" profiles are unremarkable.
# ---------------------------------------------------------------------------
OBSERVATION_PROFILES: dict[str, list[dict]] = {
    "critical_hypoxia": [
        {"label": "SpO2", "value": "87", "unit": "%"},
        {"label": "Temperature", "value": "40.2", "unit": "C"},
        {"label": "Heart rate", "value": "124", "unit": "bpm"},
    ],
    "critical_bp": [
        {"label": "Blood pressure", "value": "198/126", "unit": "mmHg"},
        {"label": "Serum creatinine", "value": "3.4", "unit": "mg/dL"},
    ],
    "severe_anaemia": [
        {"label": "Hemoglobin", "value": "6.5", "unit": "g/dL"},
        {"label": "Blood pressure", "value": "112/74", "unit": "mmHg"},
    ],
    "severe_glucose": [
        {"label": "Fasting glucose", "value": "318", "unit": "mg/dL"},
        {"label": "HbA1c", "value": "8.9", "unit": "%"},
    ],
    "severe_fever": [
        {"label": "Temperature", "value": "39.9", "unit": "C"},
        {"label": "Heart rate", "value": "98", "unit": "bpm"},
    ],
    "severe_tachycardia": [
        {"label": "Heart rate", "value": "136", "unit": "bpm"},
        {"label": "Blood pressure", "value": "104/68", "unit": "mmHg"},
    ],
    "mild_anaemia": [
        {"label": "Hemoglobin", "value": "10.4", "unit": "g/dL"},
    ],
    "mild_glycaemia": [
        {"label": "HbA1c", "value": "7.2", "unit": "%"},
    ],
    "mild_bp": [
        {"label": "Blood pressure", "value": "148/94", "unit": "mmHg"},
    ],
    "mild_lipids": [
        {"label": "LDL cholesterol", "value": "162", "unit": "mg/dL"},
    ],
    "normal_vitals": [
        {"label": "Blood pressure", "value": "118/76", "unit": "mmHg"},
        {"label": "Heart rate", "value": "78", "unit": "bpm"},
    ],
    "normal_labs": [
        {"label": "Hemoglobin", "value": "13.2", "unit": "g/dL"},
        {"label": "Fasting glucose", "value": "92", "unit": "mg/dL"},
    ],
}

#: Profile share, per 100 patients. Emergencies stay rare (as in a real OPD)
#: but never zero, and urgent is a visible minority rather than the norm.
PROFILE_MIX: tuple[tuple[str, int], ...] = (
    ("critical_hypoxia", 2),
    ("critical_bp", 2),
    ("severe_anaemia", 5),
    ("severe_glucose", 4),
    ("severe_fever", 5),
    ("severe_tachycardia", 4),
    ("mild_anaemia", 9),
    ("mild_glycaemia", 8),
    ("mild_bp", 9),
    ("mild_lipids", 7),
    ("normal_vitals", 25),
    ("normal_labs", 20),
)


# ---------------------------------------------------------------------------
# Document templates. Filenames and sizes are synthetic.
# ---------------------------------------------------------------------------
_PRIMARY_DOC_TYPES: tuple[DocumentType, ...] = (
    DocumentType.typed_note,
    DocumentType.lab_report,
    DocumentType.prescription,
    DocumentType.discharge_summary,
)

_SECONDARY_DOC_TYPES: tuple[DocumentType, ...] = (
    DocumentType.lab_report,
    DocumentType.prescription,
    DocumentType.scan_film,
)

_FAILURE_REASONS: tuple[str, ...] = (
    "Photo too blurred to read reliably (re-upload requested).",
    "Heavily compressed screenshot — no readable text or metadata.",
    "Page skewed and partly cut off; original document needed.",
)


# ---------------------------------------------------------------------------
# Planning helpers (pure — no database access)
# ---------------------------------------------------------------------------
def _scaled(count: int, size: int, floor: int) -> int:
    """Scale a per-100 count to ``size``, never dropping below ``floor``.

    ``floor`` keeps every condition bucket above the K=5 suppression threshold
    even when the cohort is seeded small.
    """
    return max(floor, round(count * size / 100))


def _language_plan(size: int, rng: random.Random) -> list[str]:
    plan: list[str] = []
    for tag, share in _LANGUAGE_MIX:
        plan.extend([tag] * _scaled(share, size, 1))
    plan = plan[:size]
    while len(plan) < size:
        plan.append("en")
    rng.shuffle(plan)
    return plan


def _profile_plan(size: int, rng: random.Random) -> list[str]:
    plan: list[str] = []
    for key, share in PROFILE_MIX:
        # Emergencies must survive a small cohort, hence the floor of 1.
        plan.extend([key] * _scaled(share, size, 1))
    plan = plan[:size]
    while len(plan) < size:
        plan.append("normal_vitals")
    rng.shuffle(plan)
    return plan


def _condition_slots(size: int) -> list[tuple[str, date]]:
    """Build every (condition label, effective date) pair the cohort will carry.

    Baseline conditions are spread thinly and evenly across weeks
    ``BASELINE_WEEK_MIN..BASELINE_WEEK_MAX``, which keeps each one's most recent
    weekly bucket well under K — so the trip-wire stays quiet for them. The
    outbreak condition gets a few scattered baseline cases plus a cluster inside
    the current week, which is what makes it, and only it, fire.
    """
    slots: list[tuple[str, date]] = []

    span = BASELINE_WEEK_MAX - BASELINE_WEEK_MIN
    for label, share in BASELINE_CONDITIONS:
        count = _scaled(share, size, 6)
        for j in range(count):
            week = BASELINE_WEEK_MIN + (j * span // max(count, 1))
            slots.append((label, _days_ago(week * 7 + (j % 5))))

    for week in OUTBREAK_BASELINE_WEEKS[
        : _scaled(OUTBREAK_BASELINE_COUNT, size, 3)
    ]:
        slots.append((OUTBREAK_CONDITION, _days_ago(week * 7 + 2)))

    # The spike sits inside the current (Monday-anchored) week so it lands in
    # the series' most recent period.
    week_start = TODAY - timedelta(days=TODAY.weekday())
    spike_days = (TODAY - week_start).days
    for j in range(_scaled(OUTBREAK_SPIKE_COUNT, size, 12)):
        slots.append((OUTBREAK_CONDITION, week_start + timedelta(days=j % (spike_days + 1))))

    return slots


def _condition_plan(size: int, rng: random.Random) -> dict[int, list[tuple[str, date]]]:
    """Distribute the condition slots over patient indices (1-2 each)."""
    slots = _condition_slots(size)
    rng.shuffle(slots)
    plan: dict[int, list[tuple[str, date]]] = defaultdict(list)
    for idx, slot in enumerate(slots):
        plan[idx % size].append(slot)
    return plan


def _name(rng: random.Random) -> tuple[str, str, str]:
    """Return (full_name, sex, region). Fabricated combinations only."""
    region = rng.choice(_REGIONS)
    sex = rng.choice(("female", "male"))
    female, male = _GIVEN_NAMES[region]
    given = rng.choice(female if sex == "female" else male)
    family = rng.choice(_FAMILY_NAMES[region])
    return f"{given} {family}", sex, region


def _abha_id(index: int) -> str:
    """Stable, cohort-only ABHA-style id. Disjoint from the showcase ids."""
    return f"{ABHA_PREFIX}-{1000 + index:04d}-{2000 + index:04d}-{3000 + index:04d}"


def _document_plan(index: int, rng: random.Random) -> list[dict]:
    """1-2 documents. Mostly verified; some extracted; a few failed.

    The first document is always readable because it carries the patient's
    clinical items — a ``failed`` document has no extractions by definition.
    """
    primary_status = (
        DocumentStatus.extracted if index % 7 == 0 else DocumentStatus.verified
    )
    doc_type = _PRIMARY_DOC_TYPES[index % len(_PRIMARY_DOC_TYPES)]
    docs: list[dict] = [
        {
            "doc_type": doc_type,
            "status": primary_status,
            "filename": f"cohort_{doc_type.value}_{index:04d}.pdf",
            "content_type": "application/pdf",
            "confidence": round(rng.uniform(0.72, 0.98), 2),
            "size_bytes": rng.randint(40_000, 320_000),
        }
    ]

    if index % 3 == 0:
        # Roughly one cohort patient in twenty brings something unreadable.
        failed = index % 21 == 0
        second_type = _SECONDARY_DOC_TYPES[index % len(_SECONDARY_DOC_TYPES)]
        docs.append(
            {
                "doc_type": second_type,
                "status": (
                    DocumentStatus.failed if failed else DocumentStatus.verified
                ),
                "filename": f"cohort_{second_type.value}_{index:04d}b.jpg",
                "content_type": "image/jpeg",
                "confidence": None if failed else round(rng.uniform(0.8, 0.97), 2),
                "size_bytes": rng.randint(30_000, 260_000),
                "error": (
                    _FAILURE_REASONS[index % len(_FAILURE_REASONS)]
                    if failed
                    else None
                ),
            }
        )
    return docs


def _extracted_text(doc_type: DocumentType, conditions: list[str]) -> str:
    listed = "; ".join(conditions) if conditions else "no active problems recorded"
    heading = doc_type.value.replace("_", " ").upper()
    return (
        f"{heading} (synthetic cohort record)\n"
        f"Recorded on file: {listed}.\n"
        "Values below are transcribed from the record for verification."
    )


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
def _item_plan(spec: dict, rng: random.Random) -> list[dict]:
    """Build every clinical item for one patient, up front and deterministically.

    Values are decided here rather than at insert time so that a partially
    seeded database still produces exactly the same rows on the next run.
    """
    out: list[dict] = []
    for label, effective in spec["conditions"]:
        out.append(
            {
                "kind": ClinicalItemKind.condition,
                "label": label,
                "value": None,
                "unit": None,
                "effective_date": effective,
                "confidence": round(rng.uniform(0.86, 0.97), 2),
            }
        )
        med = _MEDICATION_FOR.get(label) if label in _CHRONIC else None
        take_med = rng.random() < 0.65
        if med is not None and take_med:
            name, dose = med
            out.append(
                {
                    "kind": ClinicalItemKind.medication,
                    "label": name,
                    "value": dose,
                    "unit": None,
                    "effective_date": effective,
                    "confidence": round(rng.uniform(0.7, 0.96), 2),
                }
            )

    obs_date = _days_ago(rng.randint(1, 45))
    for obs in OBSERVATION_PROFILES[spec["profile"]]:
        out.append(
            {
                "kind": ClinicalItemKind.observation,
                "label": obs["label"],
                "value": obs["value"],
                "unit": obs["unit"],
                "effective_date": obs_date,
                "confidence": round(rng.uniform(0.88, 0.99), 2),
            }
        )
    return out


def _seed_patient(session, index: int, spec: dict) -> bool:
    """Insert one cohort patient. Returns True when created, False when skipped."""
    abha_id = spec["abha_id"]
    existing = session.execute(
        select(Patient.id).where(Patient.abha_id == abha_id)
    ).scalar_one_or_none()
    if existing is not None:
        return False

    age = spec["age"]
    # Backdate registration across the preceding months. This is realistic for a
    # background population, and it keeps the five showcase patients as the most
    # recently registered — the patient list is ordered newest-first, so without
    # this the cohort would bury them past the first page during a demo.
    registered_at = datetime.combine(
        TODAY - timedelta(days=30 + (index * 2) % 300),
        time(9, 0),
        tzinfo=timezone.utc,
    )
    patient = Patient(
        abha_id=abha_id,
        full_name=spec["full_name"],
        age=age,
        sex=spec["sex"],
        gender=spec["sex"],
        date_of_birth=date(TODAY.year - age, 6, 15),
        phone=f"+91-95000-{index:05d}",
        preferred_language=spec["language"],
        created_at=registered_at,
        updated_at=registered_at,
        demographics={
            "synthetic": True,
            "cohort": "background",
            "region": spec["region"],
        },
    )
    session.add(patient)
    session.flush()  # assign patient.id

    doc_specs = spec["documents"]
    condition_labels = [label for label, _ in spec["conditions"]]

    primary: Document | None = None
    for doc_spec in doc_specs:
        failed = doc_spec["status"] == DocumentStatus.failed
        document = Document(
            patient_id=patient.id,
            doc_type=doc_spec["doc_type"],
            status=doc_spec["status"],
            filename=doc_spec["filename"],
            content_type=doc_spec["content_type"],
            storage_key=f"cohort/{patient.id}/{doc_spec['filename']}",
            size_bytes=doc_spec["size_bytes"],
            extracted_text=(
                None
                if failed
                else _extracted_text(doc_spec["doc_type"], condition_labels)
            ),
            confidence=doc_spec["confidence"],
            error_reason=doc_spec.get("error"),
        )
        session.add(document)
        session.flush()  # assign document.id
        if primary is None:
            primary = document

    assert primary is not None
    # Extractions from an unverified document stay *proposed* — the
    # human-in-the-loop rule (PROJECT.md section 4.4) applies to cohort rows too.
    verified = primary.status == DocumentStatus.verified

    for item in spec["items"]:
        session.add(
            ClinicalItem(
                patient_id=patient.id,
                source_document_id=primary.id,
                kind=item["kind"],
                label=item["label"],
                value=item["value"],
                unit=item["unit"],
                data={"synthetic": True, "cohort": "background"},
                effective_date=item["effective_date"],
                confidence=item["confidence"],
                verified=verified,
            )
        )
    return True


def build_plan(size: int) -> list[dict]:
    """Build the whole deterministic cohort plan before touching the database."""
    rng = random.Random(RANDOM_SEED)
    languages = _language_plan(size, rng)
    profiles = _profile_plan(size, rng)
    conditions = _condition_plan(size, rng)

    plan: list[dict] = []
    for index in range(size):
        full_name, sex, region = _name(rng)
        spec = {
            "abha_id": _abha_id(index),
            "full_name": full_name,
            "sex": sex,
            "region": region,
            "age": rng.randint(2, 86),
            "language": languages[index],
            "profile": profiles[index],
            "conditions": sorted(conditions.get(index, []), key=lambda s: s[1]),
            "documents": _document_plan(index, rng),
        }
        spec["items"] = _item_plan(spec, rng)
        plan.append(spec)
    return plan


def seed(size: int = COHORT_SIZE) -> None:
    size = max(1, int(size))
    plan = build_plan(size)

    created = skipped = documents = items = 0
    condition_counts: Counter[str] = Counter()

    session = get_sessionmaker()()
    try:
        for index, spec in enumerate(plan):
            if _seed_patient(session, index, spec):
                created += 1
                documents += len(spec["documents"])
                items += len(spec["items"])
                condition_counts.update(
                    label for label, _ in spec["conditions"]
                )
            else:
                skipped += 1
            if (index + 1) % BATCH_SIZE == 0:
                session.commit()
        session.commit()
    finally:
        session.close()

    print(
        f"cohort seed complete: {created} patient(s) created, {skipped} already "
        f"present (skipped), {documents} document(s), {items} clinical item(s)."
    )
    if condition_counts:
        spread = ", ".join(
            f"{label} x{count}" for label, count in condition_counts.most_common()
        )
        print(f"conditions seeded: {spread}")
    print(
        "showcase patients from scripts.seed_demo are untouched "
        f"(cohort ids use the {ABHA_PREFIX}- ABHA prefix)."
    )


if __name__ == "__main__":
    requested = COHORT_SIZE
    if len(sys.argv) > 1:
        try:
            requested = int(sys.argv[1])
        except ValueError:
            raise SystemExit(
                f"usage: python -m scripts.seed_cohort [size]  "
                f"(got {sys.argv[1]!r})"
            )
    seed(requested)
