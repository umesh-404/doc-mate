# Doc-mate

**AI-assisted patient-context engine for high-volume government hospitals.**

In an Indian government OPD a patient can wait ~45 minutes for a ~5-minute consultation — and most of
those five minutes go on *reading paperwork*: old prescriptions, lab reports, discharge summaries, scan
films, handwritten notes. Diagnosis gets whatever is left.

Doc-mate ingests everything about a patient at reception (typed details, photos of documents, lab report
PDFs, scan films), indexes it, and hands the doctor a **structured, citation-backed patient snapshot they
can read in under a minute** — so the consultation goes to care, not to catching up.

> Doc-mate **summarises and cites — it never diagnoses.** The doctor stays in control, and every line is
> one click from the source document it came from.

Built for the Smart India Hackathon (SIH). All data in this repo is synthetic.

---

## The core flow

1. **Reception** creates or looks up a patient and uploads everything available, in any form.
2. The system **ingests → extracts → structures → chunks → embeds → indexes** in the background, with
   visible per-document status. Proposed medications, doses and lab values are **confirmed by a human**
   before the doctor ever sees them.
3. **Doctor** opens the patient and reads the **Patient Snapshot**: reason for visit, active problems,
   allergies (red, up top), current medications, recent labs with trends, past encounters, and a plain
   list of **flags and things to verify** — each item carrying a citation chip.

If a document could not be read, the snapshot says so. It never shows a confident summary built on
silently-dropped data.

---

## What it does

**The snapshot**
- Citation-grounded summary generation — an item with no resolvable source is dropped, not shown.
- Seven fixed sections, so the doctor's eye always lands in the same place.
- Lab trends with sparklines and direction arrows.
- A **grounding score** per summary: every generated line is graded against the text of the source it cites.

**Clinical safety**
- Offline drug–drug interaction and drug–allergy checking over a bundled reference dataset, using only
  *verified* items — an unconfirmed extraction never drives a flag.
- Neutral, cited alerts: allergies, interactions, out-of-range labs, and gaps in the record.
- Scan films get metadata, embedded text and a neutral caption — **never** a pathology read.

**Interoperability (ABDM-shaped)**
- **FHIR R4** bundle export computed from the live record (Patient, Encounter, Observation,
  MedicationRequest, AllergyIntolerance, Condition, Procedure, DocumentReference).
- **ICD-11 / NAMASTE** coding resolved offline; no match returns nothing rather than a fabricated code.
- ABHA-style patient ids, with a **mock** ABHA lookup for the demo.

**Language and voice**
- Snapshot translation into **English / Hindi / Tamil**, with clinical values, doses and citations
  preserved verbatim — if a number would be lost in translation, the original text is kept.
- A patient-facing **plain-language** narrative of the same facts.
- Voice intake, transcribed **on-device** so audio never leaves the premises.

**In the clinic**
- **Ambient consultation scribe** — capture the consult, get a draft note (subjective / objective / plan /
  follow-up / flags — there is deliberately no assessment section), and nothing enters the record until the
  doctor verifies it.
- **OPD triage** — a suggested review priority with cited reasons, and the waiting queue in both arrival
  order and suggested order. A suggestion, never a decision.

**Governance and oversight**
- **Consent** that is explicit, scoped, purpose-bound and revocable in real time (DPDP Act 2023 shaped),
  with an audited **break-glass** path so emergencies are never blocked by paperwork.
- An append-only **access audit** that carries ids, roles and coded reasons — and no patient content, ever.
- **Summary-quality evaluation**: deterministic faithfulness / completeness / conciseness scores with a
  breakdown of exactly how each number was reached.
- **Anonymised public-health surveillance** — aggregate-only, k-anonymised at K=5, ages banded, with a
  documented outbreak trip-wire that refuses to fire on a suppressed cell.

Everything above has a **deterministic offline path**: no API key, no network, same output every run.

---

## Tech stack

- **Frontend:** Next.js 14 (App Router) + TypeScript + Tailwind, TanStack Query, a small hand-rolled UI kit,
  bundled EN/HI/TA dictionaries, light + dark theme.
- **Backend:** Python 3.11 + FastAPI, SQLAlchemy 2.0 + Alembic, Pydantic v2.
- **Data:** PostgreSQL + `pgvector` — relational data and embeddings in one store.
- **Storage:** S3-compatible object storage for raw uploads (MinIO locally, R2 / Supabase in cloud).
- **AI:** provider-agnostic LLM layer via LiteLLM — cloud or self-hosted, swapped by environment variable,
  with deterministic stubs as the default.

Designed to align with India's **ABDM / ABHA + FHIR R4** health-data standards.

---

## Quickstart

```bash
docker compose -f infra/docker-compose.yml up -d     # Postgres + pgvector, MinIO

cd backend && pip install -r requirements.txt
cp .env.example .env
alembic upgrade head && python -m scripts.seed_demo  # synthetic demo dataset
uvicorn app.main:app --reload --port 8000

cd ../frontend && npm install
cp .env.example .env.local
npm run dev                                          # http://localhost:3000
```

Demo logins: `reception@demo` and `doctor@demo`, password `demo1234`.
No API keys needed — the AI layer runs on deterministic offline stubs by default.

Full instructions, ports, credentials and troubleshooting: **[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)**.

---

## Documentation

| Doc | What's in it |
|-----|--------------|
| [`docs/PROJECT.md`](docs/PROJECT.md) | **Source of truth** — problem, scope, safety principles, architecture, pipelines, data model, API surface, honest status |
| [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) | Local quickstart, ports, seeded credentials, troubleshooting |
| [`docs/DEMO.md`](docs/DEMO.md) | Demo-day runbook: the pitch, the seeded cast, the four-minute walkthrough, judge Q&A |
| [`docs/LLM.md`](docs/LLM.md) | The LLM layer: stub vs real mode, enabling a provider, running fully self-hosted |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Production runbook — Render/Fly for the backend, Vercel for the frontend |

Interactive API docs are at `/docs` on the running backend.

---

## Status and limitations

Built and working end-to-end, offline, with no keys: auth and roles, upload and ingestion, human
verification, citation-grounded snapshots with the safety pass, FHIR export, coding, translation and plain
language, voice intake, the consult scribe, consent and audit, evaluation, triage and surveillance. The
backend test suite runs fully offline; a scripted end-to-end smoke test exercises the real HTTP flow.

Be precise about what is *not* production:

- **Real LLM extraction is coded but off by default.** Without `LLM_PROVIDER` and a matching API key the
  system runs deterministic stubs — realistic-looking synthetic output, explicitly flagged, never real
  clinical reading.
- **Voice transcription is stubbed** unless `faster-whisper` and a model are installed.
- **ABHA lookup is a mock**, not NHA/ABDM integration.
- **FHIR output is schema-plausible R4**, not validator-clean — no ABDM India-profile extensions.
- **Consent enforcement is implemented and tested but not yet wired** into route dependencies; consent
  records, revocation and the audit trail are live.
- **Retrieval is exhaustive** over a patient's clinical items; the pgvector chunk index is written but not
  yet queried.
- **Not deployed.** Deploy artifacts and CI exist; there is no live URL yet.
- **API-only for now:** triage, surveillance, the consult scribe, consent/audit and evaluation have no UI.
- **Not a medical device, not ABDM-certified**, and all patient data here is synthetic.

The full breakdown is §16 of [`docs/PROJECT.md`](docs/PROJECT.md).
