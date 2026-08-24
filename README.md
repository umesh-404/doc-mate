# Doc-mate

**AI-assisted patient-context engine for high-volume government hospitals.**

In busy government hospitals a doctor gets ~5 minutes per patient — and most of it is spent reading
past records instead of diagnosing. Doc-mate ingests everything about a patient (typed details, photos
of documents, lab report PDFs, scan films), indexes it with RAG, and produces a **structured,
citation-backed patient summary** the doctor can read in under a minute — freeing those minutes for
actual diagnosis.

Built for the Smart India Hackathon (SIH).

---

## What it does

1. **Reception** creates/looks up a patient and uploads all available data in any form.
2. The system **ingests → extracts (OCR / vision) → structures → indexes** everything asynchronously.
3. **Doctor** opens the patient and sees a fast **Patient Snapshot** — active problems, medications,
   allergies, recent lab trends, past encounters, and flags — with every line linked to its source document.

> Doc-mate **summarizes and surfaces information — it never diagnoses.** The doctor stays in control,
> and every AI statement is verifiable against the original record.

## Tech stack

- **Frontend:** Next.js (App Router) + TypeScript + Tailwind
- **Backend:** Python + FastAPI
- **Data:** PostgreSQL + `pgvector` (relational data + embeddings in one store)
- **Storage:** S3-compatible object storage for raw uploads
- **AI:** provider-agnostic LLM layer (swappable cloud ↔ self-hosted models)

Designed to align with India's **ABDM / ABHA + FHIR R4** health-data standards.

## Documentation

Full architecture, data model, pipelines, and conventions live in [`docs/PROJECT.md`](docs/PROJECT.md).

## Status

Early development — see the build roadmap in the project docs.
