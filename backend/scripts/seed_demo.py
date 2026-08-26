"""Seed a rich, demo-day dataset for Doc-mate. Idempotent and offline-safe.

Run from the ``backend/`` directory, AFTER migrations, and (optionally) after
the base user seed::

    alembic upgrade head
    python -m scripts.seed_demo

What it creates
---------------
* The two demo users (``reception@demo`` / ``doctor@demo``) if missing — the
  same accounts as ``scripts.seed``, so running either first is fine.
* Six synthetic patients (clearly fake data) spanning EN / HI / TE / TA, each
  with a distinct clinical picture chosen to showcase a product strength:
    - Rukmini Devi Sharma  — diabetic + hypertensive elder, many records
                             (summarisation power).
    - Arjun Nair           — young patient, acute complaint (fast intake).
    - Meena Kumari         — antenatal patient, Hindi UI (India-scale i18n).
    - Karthik Raman        — documented Penicillin allergy, Tamil UI (safety).
    - Anasuya Pothineni    — on warfarin, arrives with an outside prescription
                             for an NSAID, Telugu UI (drug–drug interaction).
    - Lakshmi Bai          — sparse records + one unreadable upload
                             (honest flags / verify).
* Per patient: several Documents across every doc type with realistic
  filenames, confidence values and mixed statuses (mostly ``verified``, some
  ``extracted``, one ``failed`` to show faithful failure reporting).
* ClinicalItems linked to their source Document (observation / medication /
  allergy / condition / procedure), with realistic values, effective dates and
  confidence — some below 0.85 to exercise the "needs verification" path.
* Text Chunks with deterministic offline embeddings (via the LLM-layer stub),
  so retrieval works with no API keys.
* A ready-made citation-backed Summary per patient (the 7 PROJECT.md sections),
  so the doctor Snapshot screen looks great the instant the stack boots.

Safety (PROJECT.md section 4) is respected by construction:
* Allergies are surfaced prominently (severity ``high``).
* Every non-``flags`` summary item cites a REAL seeded document id.
* No diagnosis / treatment language — only reasons-for-visit and neutral facts.
* Low-confidence / unverified items are flagged for verification, never
  presented as certain, and never fabricated.

Idempotency
-----------
Patients are keyed by their (synthetic) ABHA id and users by email. Re-running
the script skips anything already present, so it is safe to run repeatedly and
to use as the demo "reset" step. Requires a reachable database (DATABASE_URL);
no database connection is opened at import time.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import (
    Chunk,
    ClinicalItem,
    ClinicalItemKind,
    ConsentScope,
    Document,
    DocumentStatus,
    DocumentType,
    Patient,
    Summary,
    User,
    UserRole,
)
from app.db.session import get_sessionmaker
from app.governance import get_latest_consent, grant_consent
from app.ingestion.pipeline import _citation_label, chunk_text
from app.llm import stub
from app.safety.alerts import build_alerts

TODAY = date.today()


def _days_ago(n: int) -> date:
    return TODAY - timedelta(days=n)


# ---------------------------------------------------------------------------
# Demo users (mirror scripts.seed so either seeder can run first).
# ---------------------------------------------------------------------------
DEMO_USERS = [
    {
        "email": "reception@demo",
        "full_name": "Reception Demo",
        "role": UserRole.reception,
        "password": "demo1234",
    },
    {
        "email": "doctor@demo",
        "full_name": "Doctor Demo",
        "role": UserRole.doctor,
        "password": "demo1234",
    },
]


# ---------------------------------------------------------------------------
# Synthetic patient dataset. All data below is fabricated for the demo — no
# real person, ABHA id, or record is represented.
#
# Each document carries a "key" so its clinical items and the summary complaint
# can reference the exact source document after ids are assigned at insert.
# Item fields: kind, label, value, unit, days_ago, confidence, verified, and
# optional presentation hints (severity, trend).
# ---------------------------------------------------------------------------
PATIENTS: list[dict] = [
    # -- 1. Rich elder: the summarisation showcase ------------------------
    {
        "abha_id": "11-2233-4455-6677",
        "full_name": "Rukmini Devi Sharma",
        "age": 68,
        "sex": "female",
        "gender": "female",
        "phone": "+91-90000-10001",
        "preferred_language": "en",
        "demographics": {
            "synthetic": True,
            "address": "Ward 4, Old City (synthetic)",
            "emergency_contact": "Son — +91-90000-10099 (synthetic)",
        },
        "complaint": {
            "text": "Routine follow-up for diabetes and blood-pressure control; "
            "reports occasional giddiness.",
            "doc": "rx",
        },
        "documents": [
            {
                "key": "rx",
                "doc_type": DocumentType.prescription,
                "status": DocumentStatus.verified,
                "filename": "rx_endocrine_clinic_2026-04.jpg",
                "content_type": "image/jpeg",
                "confidence": 0.94,
                "size_bytes": 412_337,
                "extracted_text": (
                    "PRESCRIPTION (demo)\nMetformin 500mg 1-0-1\n"
                    "Amlodipine 5mg 1-0-0\nAtorvastatin 10mg 0-0-1\n"
                    "Review after 3 months."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Metformin 500mg",
                        "value": "1-0-1",
                        "days_ago": 120,
                        "confidence": 0.96,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Amlodipine 5mg",
                        "value": "1-0-0",
                        "days_ago": 120,
                        "confidence": 0.93,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Atorvastatin 10mg",
                        "value": "0-0-1",
                        "days_ago": 120,
                        "confidence": 0.82,  # < 0.85 -> verify flag
                        "verified": True,
                    },
                ],
            },
            {
                "key": "lab_recent",
                "doc_type": DocumentType.lab_report,
                "status": DocumentStatus.verified,
                "filename": "labs_biochem_2026-04-18.pdf",
                "content_type": "application/pdf",
                "confidence": 0.97,
                "size_bytes": 88_204,
                "extracted_text": (
                    "LABORATORY REPORT (demo)\nHbA1c 7.8 %\n"
                    "Fasting glucose 142 mg/dL\nLDL cholesterol 132 mg/dL\n"
                    "Serum creatinine 1.1 mg/dL"
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "HbA1c",
                        "value": "7.8",
                        "unit": "%",
                        "days_ago": 128,
                        "confidence": 0.98,
                        "verified": True,
                        "trend": "up",
                    },
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "Fasting glucose",
                        "value": "142",
                        "unit": "mg/dL",
                        "days_ago": 128,
                        "confidence": 0.97,
                        "verified": True,
                        "trend": "up",
                    },
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "LDL cholesterol",
                        "value": "132",
                        "unit": "mg/dL",
                        "days_ago": 128,
                        "confidence": 0.95,
                        "verified": True,
                        "trend": "flat",
                    },
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "Serum creatinine",
                        "value": "1.1",
                        "unit": "mg/dL",
                        "days_ago": 128,
                        "confidence": 0.96,
                        "verified": True,
                        "trend": "flat",
                    },
                ],
            },
            {
                "key": "discharge",
                "doc_type": DocumentType.discharge_summary,
                "status": DocumentStatus.verified,
                "filename": "discharge_cardiology_2025-11.pdf",
                "content_type": "application/pdf",
                "confidence": 0.9,
                "size_bytes": 154_902,
                "extracted_text": (
                    "DISCHARGE SUMMARY (demo)\n"
                    "Type 2 diabetes mellitus\nEssential hypertension\n"
                    "Coronary angiography (2025-11-09)\n"
                    "Discharged stable on oral medication."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.condition,
                        "label": "Type 2 diabetes mellitus",
                        "days_ago": 289,
                        "confidence": 0.94,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.condition,
                        "label": "Essential hypertension",
                        "days_ago": 289,
                        "confidence": 0.92,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.procedure,
                        "label": "Coronary angiography",
                        "days_ago": 289,
                        "confidence": 0.9,
                        "verified": True,
                    },
                ],
            },
            {
                "key": "lab_old",
                "doc_type": DocumentType.lab_report,
                "status": DocumentStatus.verified,
                "filename": "labs_biochem_2025-10-02.pdf",
                "content_type": "application/pdf",
                "confidence": 0.95,
                "size_bytes": 81_110,
                "extracted_text": (
                    "LABORATORY REPORT (demo)\nHbA1c 8.4 %\n"
                    "LDL cholesterol 141 mg/dL"
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "HbA1c (prior)",
                        "value": "8.4",
                        "unit": "%",
                        "days_ago": 327,
                        "confidence": 0.95,
                        "verified": True,
                        "trend": "down",  # improved vs prior reading
                    },
                ],
            },
            {
                "key": "ecg_scan",
                "doc_type": DocumentType.scan_film,
                "status": DocumentStatus.extracted,  # awaiting reception verify
                "filename": "ecg_strip_2026-04-18.png",
                "content_type": "image/png",
                "confidence": 0.71,
                "size_bytes": 233_540,
                "extracted_text": (
                    "IMAGING (demo)\nECG strip captured; neutral caption only "
                    "(not a diagnosis)."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "ECG strip, lead II",
                        "value": "Image captured; neutral caption only "
                        "(not a diagnosis).",
                        "days_ago": 128,
                        "confidence": 0.66,
                        "verified": False,  # -> flags
                    },
                ],
            },
            {
                "key": "old_film_failed",
                "doc_type": DocumentType.scan_film,
                "status": DocumentStatus.failed,
                "filename": "chest_xray_scanned_photo.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 74_881,
                "error": "Image too dark and skewed to read reliably "
                "(re-upload a clearer photo requested).",
                "items": [],
            },
        ],
        "extra_flags": [
            "Reported giddiness has no vitals attached yet — capture BP / "
            "pulse at intake.",
        ],
    },
    # -- 2. Young acute complaint: fast intake ----------------------------
    {
        "abha_id": "22-3344-5566-7788",
        "full_name": "Arjun Nair",
        "age": 24,
        "sex": "male",
        "gender": "male",
        "phone": "+91-90000-20002",
        "preferred_language": "en",
        "demographics": {
            "synthetic": True,
            "occupation": "Student (synthetic)",
        },
        "complaint": {
            "text": "Three days of fever, sore throat and body ache; here for "
            "assessment.",
            "doc": "note",
        },
        "documents": [
            {
                "key": "note",
                "doc_type": DocumentType.typed_note,
                "status": DocumentStatus.verified,
                "filename": "intake_note_2026-08-24.txt",
                "content_type": "text/plain",
                "confidence": 0.99,
                "size_bytes": 1_204,
                "extracted_text": (
                    "CLINICAL NOTE (demo)\n"
                    "Fever up to 101F for 3 days, sore throat, myalgia. "
                    "No breathlessness. No known chronic illness."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "Temperature",
                        "value": "101",
                        "unit": "F",
                        "days_ago": 1,
                        "confidence": 0.99,
                        "verified": True,
                        "trend": "up",
                    },
                    {
                        "kind": ClinicalItemKind.condition,
                        "label": "Acute febrile illness (reason for visit)",
                        "days_ago": 1,
                        "confidence": 0.9,
                        "verified": True,
                    },
                ],
            },
            {
                "key": "rx",
                "doc_type": DocumentType.prescription,
                "status": DocumentStatus.extracted,  # OCR proposed, not verified
                "filename": "otc_slip_photo.jpg",
                "content_type": "image/jpeg",
                "confidence": 0.68,
                "size_bytes": 190_442,
                "extracted_text": (
                    "PRESCRIPTION (demo)\nParacetamol 500mg PRN (handwritten, "
                    "partly legible)."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Paracetamol 500mg",
                        "value": "PRN",
                        "days_ago": 2,
                        "confidence": 0.64,
                        "verified": False,  # -> flags (handwriting)
                    },
                ],
            },
        ],
        "extra_flags": [
            "No prior records on file — first documented visit for this "
            "patient.",
        ],
    },
    # -- 3. Antenatal patient: Hindi UI, India-scale i18n -----------------
    {
        "abha_id": "33-4455-6677-8899",
        "full_name": "Meena Kumari",
        "age": 27,
        "sex": "female",
        "gender": "female",
        "phone": "+91-90000-30003",
        "preferred_language": "hi",
        "demographics": {
            "synthetic": True,
            "note": "Antenatal follow-up (synthetic)",
        },
        "complaint": {
            "text": "Antenatal check-up at ~28 weeks; routine review, no acute "
            "complaint.",
            "doc": "anc_note",
        },
        "documents": [
            {
                "key": "anc_note",
                "doc_type": DocumentType.typed_note,
                "status": DocumentStatus.verified,
                "filename": "anc_visit_2026-08-10.txt",
                "content_type": "text/plain",
                "confidence": 0.97,
                "size_bytes": 1_602,
                "extracted_text": (
                    "CLINICAL NOTE (demo)\n"
                    "Antenatal visit, gravida 1. ~28 weeks by dates. "
                    "BP 118/76. On routine iron and folic acid supplements."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.condition,
                        "label": "Pregnancy, antenatal follow-up",
                        "days_ago": 14,
                        "confidence": 0.95,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Iron + folic acid (antenatal)",
                        "value": "1-0-0",
                        "days_ago": 14,
                        "confidence": 0.9,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "Blood pressure",
                        "value": "118/76",
                        "unit": "mmHg",
                        "days_ago": 14,
                        "confidence": 0.94,
                        "verified": True,
                        "trend": "flat",
                    },
                ],
            },
            {
                "key": "anc_labs",
                "doc_type": DocumentType.lab_report,
                "status": DocumentStatus.verified,
                "filename": "anc_bloodwork_2026-08-10.pdf",
                "content_type": "application/pdf",
                "confidence": 0.96,
                "size_bytes": 76_330,
                "extracted_text": (
                    "LABORATORY REPORT (demo)\nHemoglobin 10.6 g/dL\n"
                    "Blood group O positive\nRandom glucose 96 mg/dL"
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "Hemoglobin",
                        "value": "10.6",
                        "unit": "g/dL",
                        "days_ago": 14,
                        "confidence": 0.96,
                        "verified": True,
                        "trend": "down",  # mild anaemia, watch
                    },
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "Blood group",
                        "value": "O positive",
                        "days_ago": 14,
                        "confidence": 0.98,
                        "verified": True,
                    },
                ],
            },
            {
                "key": "usg",
                "doc_type": DocumentType.scan_film,
                "status": DocumentStatus.extracted,
                "filename": "obstetric_ultrasound_2026-08-10.png",
                "content_type": "image/png",
                "confidence": 0.74,
                "size_bytes": 288_771,
                "extracted_text": (
                    "IMAGING (demo)\nObstetric ultrasound; neutral caption "
                    "only (not a diagnosis)."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "Obstetric ultrasound",
                        "value": "Image captured; neutral caption only "
                        "(not a diagnosis).",
                        "days_ago": 14,
                        "confidence": 0.7,
                        "verified": False,  # -> flags
                    },
                ],
            },
        ],
        "extra_flags": [
            "Hemoglobin 10.6 g/dL is on the low side for pregnancy — confirm "
            "trend against earlier antenatal bloodwork.",
        ],
    },
    # -- 4. Drug allergy: the safety showcase, Tamil UI -------------------
    {
        "abha_id": "44-5566-7788-9900",
        "full_name": "Karthik Raman",
        "age": 45,
        "sex": "male",
        "gender": "male",
        "phone": "+91-90000-40004",
        "preferred_language": "ta",
        "demographics": {
            "synthetic": True,
            "note": "Documented drug allergy (synthetic)",
        },
        "complaint": {
            "text": "Follow-up after treated skin infection; here to review "
            "healing and medication.",
            "doc": "discharge",
        },
        "documents": [
            {
                "key": "discharge",
                "doc_type": DocumentType.discharge_summary,
                "status": DocumentStatus.verified,
                "filename": "discharge_2026-07-15.pdf",
                "content_type": "application/pdf",
                "confidence": 0.95,
                "size_bytes": 132_004,
                "extracted_text": (
                    "DISCHARGE SUMMARY (demo)\n"
                    "ALLERGY: Penicillin — documented rash reaction.\n"
                    "Cellulitis, right leg, treated.\n"
                    "Incision and drainage performed."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.allergy,
                        "label": "Penicillin",
                        "value": "Rash / hypersensitivity reaction",
                        "days_ago": 40,
                        "confidence": 0.97,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.condition,
                        "label": "Cellulitis, right leg (treated)",
                        "days_ago": 40,
                        "confidence": 0.93,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.procedure,
                        "label": "Incision and drainage",
                        "days_ago": 40,
                        "confidence": 0.9,
                        "verified": True,
                    },
                ],
            },
            {
                "key": "rx",
                "doc_type": DocumentType.prescription,
                "status": DocumentStatus.verified,
                "filename": "rx_2026-07-15.jpg",
                "content_type": "image/jpeg",
                "confidence": 0.91,
                "size_bytes": 205_118,
                "extracted_text": (
                    "PRESCRIPTION (demo)\nAzithromycin 500mg 1-0-0 x3 days\n"
                    "(non-penicillin antibiotic chosen due to allergy)."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Azithromycin 500mg",
                        "value": "1-0-0",
                        "days_ago": 40,
                        "confidence": 0.92,
                        "verified": True,
                    },
                ],
            },
        ],
        "extra_flags": [],
    },
    # -- 5. Drug–drug interaction: medication safety, Telugu UI -----------
    #
    # Karthik covers drug–ALLERGY. This patient covers the other half of the
    # safety pass: a drug–DRUG interaction between two records issued by
    # different facilities — exactly the collision a doctor reading a thick
    # paper file is most likely to miss. Both medications are verified,
    # because app.safety.interactions deliberately ignores unconfirmed
    # extractions (PROJECT.md section 6c): an unverified pair raises nothing.
    {
        "abha_id": "66-7788-9900-1122",
        "full_name": "Anasuya Pothineni",
        "age": 62,
        "sex": "female",
        "gender": "female",
        "phone": "+91-90000-60006",
        "preferred_language": "te",
        "demographics": {
            "synthetic": True,
            "address": "Ward 9, rural referral block (synthetic)",
            "note": "On long-term anticoagulation (synthetic)",
        },
        "complaint": {
            "text": "Knee and lower-back pain for two weeks; brought a "
            "prescription from an outside clinic and is here for review of "
            "her regular medication.",
            "doc": "outside_rx",
        },
        "documents": [
            {
                "key": "discharge",
                "doc_type": DocumentType.discharge_summary,
                "status": DocumentStatus.verified,
                "filename": "discharge_cardiology_2026-05-20.pdf",
                "content_type": "application/pdf",
                "confidence": 0.96,
                "size_bytes": 147_663,
                "extracted_text": (
                    "DISCHARGE SUMMARY (demo)\n"
                    "Atrial fibrillation, rate controlled.\n"
                    "Warfarin 3mg 0-0-1, INR monitored monthly.\n"
                    "Metoprolol 25mg 1-0-1.\n"
                    "Discharged stable on oral medication."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.condition,
                        "label": "Atrial fibrillation",
                        "days_ago": 98,
                        "confidence": 0.94,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Warfarin 3mg",
                        "value": "0-0-1",
                        "days_ago": 98,
                        "confidence": 0.95,
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Metoprolol 25mg",
                        "value": "1-0-1",
                        "days_ago": 98,
                        "confidence": 0.93,
                        "verified": True,
                    },
                ],
            },
            {
                "key": "inr_lab",
                "doc_type": DocumentType.lab_report,
                "status": DocumentStatus.verified,
                "filename": "labs_coagulation_2026-08-12.pdf",
                "content_type": "application/pdf",
                "confidence": 0.97,
                "size_bytes": 71_408,
                "extracted_text": (
                    "LABORATORY REPORT (demo)\nINR 3.4\n"
                    "Hemoglobin 11.1 g/dL\nPlatelet count 214000 /uL"
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "INR",
                        "value": "3.4",
                        "days_ago": 12,
                        "confidence": 0.97,
                        "verified": True,
                        "trend": "up",
                    },
                    {
                        "kind": ClinicalItemKind.observation,
                        "label": "Hemoglobin",
                        "value": "11.1",
                        "unit": "g/dL",
                        "days_ago": 12,
                        "confidence": 0.96,
                        "verified": True,
                        "trend": "down",
                    },
                ],
            },
            {
                "key": "outside_rx",
                "doc_type": DocumentType.prescription,
                "status": DocumentStatus.verified,  # confirmed at reception
                "filename": "outside_clinic_rx_photo_2026-08-18.jpg",
                "content_type": "image/jpeg",
                "confidence": 0.86,
                "size_bytes": 221_775,
                "extracted_text": (
                    "PRESCRIPTION (demo)\nDiclofenac 50mg 1-0-1 x5 days for "
                    "joint pain\nPantoprazole 40mg 1-0-0\n"
                    "(issued at an outside clinic; anticoagulant not listed)."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Diclofenac 50mg",
                        "value": "1-0-1",
                        "days_ago": 6,
                        "confidence": 0.84,  # < 0.85 -> verify flag
                        "verified": True,
                    },
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Pantoprazole 40mg",
                        "value": "1-0-0",
                        "days_ago": 6,
                        "confidence": 0.88,
                        "verified": True,
                    },
                ],
            },
        ],
        "extra_flags": [
            "The outside prescription and the discharge medication list come "
            "from different facilities — confirm with the patient what she is "
            "actually taking today.",
            "No INR reading on file since the outside prescription was issued.",
        ],
    },
    # -- 6. Sparse records: honest flags / verify -------------------------
    {
        "abha_id": "55-6677-8899-0011",
        "full_name": "Lakshmi Bai",
        "age": 55,
        "sex": "female",
        "gender": "female",
        "phone": "+91-90000-50005",
        "preferred_language": "hi",
        "demographics": {
            "synthetic": True,
            "note": "Sparse record — referred from another facility "
            "(synthetic)",
        },
        "complaint": {
            "text": "Referred for knee pain; brought only a photo of an older "
            "prescription.",
            "doc": "old_rx",
        },
        "documents": [
            {
                "key": "old_rx",
                "doc_type": DocumentType.prescription,
                "status": DocumentStatus.extracted,  # legible-ish, low conf
                "filename": "old_prescription_photo.jpg",
                "content_type": "image/jpeg",
                "confidence": 0.61,
                "size_bytes": 168_923,
                "extracted_text": (
                    "PRESCRIPTION (demo)\nPantoprazole 40mg 1-0-0 (faded, "
                    "partly legible)."
                ),
                "items": [
                    {
                        "kind": ClinicalItemKind.medication,
                        "label": "Pantoprazole 40mg",
                        "value": "1-0-0",
                        "days_ago": 210,
                        "confidence": 0.58,
                        "verified": False,  # -> flags
                    },
                ],
            },
            {
                "key": "referral_scan",
                "doc_type": DocumentType.scan_film,
                "status": DocumentStatus.failed,
                "filename": "knee_xray_whatsapp.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 41_260,
                "error": "Heavily compressed screenshot — no readable metadata "
                "or text (request original film).",
                "items": [],
            },
        ],
        "extra_flags": [
            "Very little history on file — allergies, chronic conditions and "
            "current medications are UNKNOWN; confirm verbally at intake.",
            "No vitals or recent labs on record for this patient.",
        ],
    },
]


# ---------------------------------------------------------------------------
# Summary assembly (mirrors the app's citation + safety rules).
# ---------------------------------------------------------------------------
_SECTION_TITLES: dict[str, str] = {
    "complaint": "Current complaint / reason for visit",
    "problems": "Active problems & chronic conditions",
    "allergies": "Allergies",
    "medications": "Current medications",
    "labs": "Recent labs & trends",
    "encounters": "Past encounters / procedures",
    "flags": "Flags & things to verify",
}
_SECTION_ORDER = [
    "complaint",
    "problems",
    "allergies",
    "medications",
    "labs",
    "encounters",
    "flags",
]
_KIND_TO_SECTION = {
    ClinicalItemKind.condition: "problems",
    ClinicalItemKind.allergy: "allergies",
    ClinicalItemKind.medication: "medications",
    ClinicalItemKind.observation: "labs",
    ClinicalItemKind.procedure: "encounters",
}
_VERIFY_THRESHOLD = 0.85


def _item_text(kind: ClinicalItemKind, label: str, value, unit) -> str:
    if kind == ClinicalItemKind.medication:
        return f"{label} — {value}" if value else label
    if kind == ClinicalItemKind.observation:
        if value and unit:
            return f"{label}: {value} {unit}"
        if value:
            return f"{label}: {value}"
        return label
    return label


def _build_sections(ctx_items: list[dict], complaint: dict, extra_flags: list[str]) -> list[dict]:
    """Build the 7 structured sections. Every non-flags item cites a real doc."""
    buckets: dict[str, list[dict]] = {k: [] for k in _SECTION_ORDER}

    # Complaint (reason for visit) — always cited to a real source document.
    if complaint:
        buckets["complaint"].append(
            {
                "text": complaint["text"],
                "severity": "med",
                "verified": True,
                "citations": [
                    {"document_id": complaint["doc_id"], "label": complaint["label"]}
                ],
            }
        )

    for it in ctx_items:
        kind: ClinicalItemKind = it["kind"]
        citation = {"document_id": it["document_id"], "label": it["citation_label"]}
        text = _item_text(kind, it["label"], it.get("value"), it.get("unit"))

        if it["verified"]:
            section = _KIND_TO_SECTION.get(kind)
            if section is not None:
                summary_item: dict = {
                    "text": text,
                    "confidence": it.get("confidence"),
                    "verified": True,
                    "citations": [citation],
                }
                if kind == ClinicalItemKind.allergy:
                    summary_item["severity"] = "high"
                elif kind == ClinicalItemKind.condition:
                    summary_item["severity"] = "med"
                elif kind == ClinicalItemKind.observation and it.get("trend"):
                    summary_item["trend"] = it["trend"]
                buckets[section].append(summary_item)

            # Verified but low-confidence -> also surface a verify flag.
            conf = it.get("confidence")
            if conf is not None and conf < _VERIFY_THRESHOLD:
                buckets["flags"].append(
                    {
                        "text": f"Low-confidence {kind.value}: {text} — "
                        "double-check against the source document.",
                        "severity": "low",
                        "confidence": conf,
                        "verified": True,
                        "citations": [citation],
                    }
                )
        else:
            # Unverified extraction -> proposed only, goes to flags.
            buckets["flags"].append(
                {
                    "text": f"Unverified {kind.value}: {text} — confirm at "
                    "reception before use.",
                    "severity": "low",
                    "confidence": it.get("confidence"),
                    "verified": False,
                    "citations": [citation],
                }
            )

    # Narrative flags (missing data, unreadable uploads). Citations optional.
    for note in extra_flags:
        buckets["flags"].append(
            {"text": note, "severity": "low", "verified": False, "citations": []}
        )

    return [
        {"key": key, "title": _SECTION_TITLES[key], "items": buckets[key]}
        for key in _SECTION_ORDER
    ]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
def _seed_users(session) -> None:
    for spec in DEMO_USERS:
        existing = session.execute(
            select(User).where(User.email == spec["email"])
        ).scalar_one_or_none()
        if existing is not None:
            print(f"user exists: {spec['email']} ({spec['role'].value})")
            continue
        session.add(
            User(
                email=spec["email"],
                full_name=spec["full_name"],
                role=spec["role"],
                hashed_password=hash_password(spec["password"]),
                is_active=True,
            )
        )
        print(f"user created: {spec['email']} ({spec['role'].value})")
    session.commit()


def _seed_consent(session, patient) -> None:
    """Record explicit consent for a seeded patient (idempotent).

    Sensitive reads run through the consent gate (``CONSENT_ENFORCEMENT``), so
    seeded patients carry a real granted consent: the demo behaves identically
    in ``audit_only`` and ``enforce`` mode, and the governance screens have
    genuine rows to show. ``purpose`` is a staff-authored label, never patient
    content.
    """
    if get_latest_consent(session, patient.id) is not None:
        return
    granted_by = session.execute(
        select(User).where(User.email == "reception@demo")
    ).scalar_one_or_none()
    grant_consent(
        session,
        patient.id,
        scope=ConsentScope.full_record,
        purpose="outpatient consultation",
        granted_by=granted_by,
    )


def _seed_patient(session, spec: dict) -> None:
    existing = session.execute(
        select(Patient).where(Patient.abha_id == spec["abha_id"])
    ).scalar_one_or_none()
    if existing is not None:
        # Still ensure consent exists — re-running the seeder must leave an
        # already-seeded patient fully usable under CONSENT_ENFORCEMENT=enforce.
        _seed_consent(session, existing)
        print(f"patient exists: {spec['full_name']} ({spec['abha_id']})")
        return

    patient = Patient(
        abha_id=spec["abha_id"],
        full_name=spec["full_name"],
        age=spec["age"],
        sex=spec.get("sex"),
        gender=spec.get("gender"),
        date_of_birth=date(TODAY.year - spec["age"], 6, 15),
        phone=spec.get("phone"),
        preferred_language=spec["preferred_language"],
        demographics=spec.get("demographics"),
    )
    session.add(patient)
    session.flush()  # assign patient.id

    doc_by_key: dict[str, Document] = {}
    ctx_items: list[dict] = []

    for doc_spec in spec["documents"]:
        document = Document(
            patient_id=patient.id,
            doc_type=doc_spec["doc_type"],
            status=doc_spec["status"],
            filename=doc_spec.get("filename"),
            content_type=doc_spec.get("content_type"),
            storage_key=f"demo/{patient.id}/{doc_spec.get('filename', 'file')}",
            size_bytes=doc_spec.get("size_bytes"),
            extracted_text=doc_spec.get("extracted_text"),
            confidence=doc_spec.get("confidence"),
            error_reason=doc_spec.get("error"),
        )
        session.add(document)
        session.flush()  # assign document.id
        doc_by_key[doc_spec["key"]] = document

        # Clinical items linked to this source document.
        item_dates: list[date] = []
        for raw in doc_spec.get("items", []):
            eff = _days_ago(raw["days_ago"]) if raw.get("days_ago") is not None else None
            if eff is not None:
                item_dates.append(eff)
            session.add(
                ClinicalItem(
                    patient_id=patient.id,
                    source_document_id=document.id,
                    kind=raw["kind"],
                    label=raw["label"],
                    value=raw.get("value"),
                    unit=raw.get("unit"),
                    data={"synthetic": True},
                    effective_date=eff,
                    confidence=raw.get("confidence"),
                    verified=raw.get("verified", False),
                )
            )
            ctx_items.append(
                {
                    "kind": raw["kind"],
                    "label": raw["label"],
                    "value": raw.get("value"),
                    "unit": raw.get("unit"),
                    "confidence": raw.get("confidence"),
                    "verified": raw.get("verified", False),
                    "trend": raw.get("trend"),
                    "document_id": str(document.id),
                    "citation_label": _citation_label(document.doc_type, eff),
                }
            )

        # Chunks + deterministic offline embeddings (only for readable docs).
        text = doc_spec.get("extracted_text")
        if doc_spec["status"] != DocumentStatus.failed and text:
            chunks = chunk_text(text)
            embeddings = stub.embed(chunks) if chunks else []
            doc_date = max(item_dates) if item_dates else None
            label = _citation_label(document.doc_type, doc_date)
            for chunk_str, vector in zip(chunks, embeddings):
                session.add(
                    Chunk(
                        patient_id=patient.id,
                        document_id=document.id,
                        text=chunk_str,
                        embedding=vector,
                        doc_type=document.doc_type,
                        doc_date=doc_date,
                        citation_anchor={
                            "label": label,
                            "doc_type": document.doc_type.value,
                            "date": doc_date.isoformat() if doc_date else None,
                        },
                    )
                )

    # Resolve the complaint's source document, then build + persist a summary.
    complaint_spec = spec.get("complaint")
    complaint: dict = {}
    if complaint_spec:
        cdoc = doc_by_key[complaint_spec["doc"]]
        complaint = {
            "text": complaint_spec["text"],
            "doc_id": str(cdoc.id),
            "label": _citation_label(cdoc.doc_type, None),
        }

    sections = _build_sections(ctx_items, complaint, spec.get("extra_flags", []))
    # Compute the same citation-backed safety alerts the live pipeline produces,
    # so the doctor snapshot's alerts banner is populated for seeded patients too.
    # build_alerts expects `kind` as the string value (matching gather_context),
    # so normalize any enum members before passing them in.
    alert_ctx = [
        {**it, "kind": getattr(it.get("kind"), "value", it.get("kind"))}
        for it in ctx_items
    ]
    alerts = build_alerts(alert_ctx)
    session.add(
        Summary(
            patient_id=patient.id,
            encounter_id=None,
            language=spec["preferred_language"],
            sections=sections,
            generation_metadata={
                "mode": "stub",
                "source": "seed_demo",
                "fact_count": len(ctx_items),
                "alerts": alerts,
            },
        )
    )
    session.commit()

    _seed_consent(session, patient)

    doc_count = len(spec["documents"])
    item_count = sum(len(d.get("items", [])) for d in spec["documents"])
    print(
        f"patient created: {spec['full_name']} ({spec['abha_id']}) — "
        f"{doc_count} docs, {item_count} items, summary ready"
    )


def seed() -> None:
    session = get_sessionmaker()()
    try:
        _seed_users(session)
        for spec in PATIENTS:
            _seed_patient(session, spec)
    finally:
        session.close()
    print("demo seed complete.")


if __name__ == "__main__":
    seed()
