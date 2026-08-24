# Doc-mate

> AI-assisted patient-context engine for high-volume government hospitals.
> Give the doctor everything about a patient in **under 1 minute**, so the 5-minute
> consultation is spent on diagnosis, not on reading paperwork.

This file is the source of truth for how we build Doc-mate. Read it fully before writing code.
Keep it updated as decisions change.

---

## 1. The problem (why this exists)

Government hospitals in India have enormous patient inflow. A doctor gets ~5 minutes per patient.
In those 5 minutes the doctor must:

1. Read all the patient's past + present records (prescriptions, lab reports, scans, discharge summaries, complaints).
2. Understand the current problem.
3. Diagnose and prescribe.

Step 1 alone eats most of the 5 minutes. If the doctor could absorb the full patient picture in **under 1 minute**,
the remaining 4 minutes go to actual diagnosis — a massive productivity gain, at India scale.

**Doc-mate closes that gap.** At intake, front-desk staff upload/type everything about the patient
(typed details, photos of documents, lab PDFs, scan films). The system ingests, processes, indexes (RAG),
and produces a **structured, citation-backed patient summary** the doctor can read top-to-bottom in seconds.

---

## 2. What we are building (scope)

**Target: a polished, end-to-end demo/prototype for Smart India Hackathon (SIH).**
Seeded/synthetic hospital data. Not ABDM-certified — but architected so ABDM/ABHA + FHIR can slot in later.

### The core demo flow (this is the product — everything serves it)
1. **Reception** creates a patient (or looks one up) and uploads all available data in any form.
2. System **ingests + processes + indexes** everything asynchronously (with visible status).
3. **Doctor** opens the patient and sees a fast, high-polish **Patient Snapshot** — a summary they can read in <1 min,
   with every claim linked back to its source document.
4. Doctor diagnoses faster. Done.

### In scope
- All input forms: **typed/structured entry, photos of documents, medical scan films (X-ray/MRI/CT), lab report PDFs.**
- RAG-based indexing + retrieval over a patient's longitudinal record.
- Structured patient summary generation **with citations** to source documents.
- Two roles: **Reception** (create patient, upload) and **Doctor** (read snapshot). Simple JWT auth.
- Languages: **English + Hindi + one regional language** (e.g. Tamil or Bengali) for summaries and input handling.
- Cloud-deployed so judges can try it live. High-polish doctor UI.

### Explicit non-goals (do NOT build these)
- ❌ **The AI never states a diagnosis or treatment.** It summarizes and surfaces; the doctor diagnoses. (See §4.)
- ❌ Not a regulated medical device. No autonomous clinical decisions.
- ❌ No real ABDM certification for the hackathon (design for it, don't certify).
- ❌ No full multilingual coverage of all Indian languages (roadmap item).
- ❌ No real patient PII. Use synthetic/consented demo data only.

---

## 3. India healthcare context (know this — it wins SIH points)

- **ABDM** (Ayushman Bharat Digital Mission): India's national digital health infra, run by the National Health Authority (NHA).
- **ABHA** (Ayushman Bharat Health Account): a 14-digit patient health ID that links records across providers under patient consent.
- **FHIR R4**: the interoperability standard ABDM uses (via the ABDM FHIR Implementation Guide). Records are exchanged as FHIR resources.
- **HIP/HIU**: Health Information Provider / User — the roles for publishing/consuming records via consent.
- **NAMASTE / ICD-11 (TM2)**: coding systems relevant to Indian EMR compliance.

**Our stance:** model our internal patient/document data so it maps cleanly onto **FHIR resources**
(Patient, Encounter, Observation, DiagnosticReport, MedicationRequest, AllergyIntolerance, DocumentReference).
Use ABHA-style IDs for patients. This makes "ABDM-ready" an honest claim and makes future integration a plumbing job, not a rewrite.

---

## 4. Safety & trust principles (NON-NEGOTIABLE)

These are the rules that make Doc-mate usable by real doctors. Violating them fails the project.

1. **No diagnosis, no treatment advice.** The AI organizes, summarizes, and highlights. It never concludes.
   UI must never phrase output as a clinical conclusion.
2. **Never invent clinical values.** Medication names, dosages, lab values, dates — these are extracted, never guessed.
   If a value is uncertain or unreadable, mark it `⚠ needs verification`, never fabricate.
3. **Everything is cited.** Every line in the summary links to the exact source document (and ideally the region/page).
   No citation → it doesn't go in the summary. Doctors must be able to verify in one click.
4. **Human-in-the-loop on extraction.** OCR on medical handwriting is ~82–95% accurate at best. Extracted structured
   fields (esp. meds/doses) are shown as *proposed* and are verifiable/editable at reception before the doctor sees them.
5. **Faithful status reporting.** If ingestion failed or a doc couldn't be read, say so plainly in the UI. Never show a
   confident summary built on silently-dropped data.
6. **Privacy first.** No patient data in logs, URLs, or query strings. Design for de-identification. Treat all patient
   content as sensitive even in the demo.
7. **Scans are indexed/captioned, not diagnosed.** For X-ray/MRI/CT films we extract metadata, any embedded text, and a
   neutral descriptive caption — we do NOT read them for pathology.

When in doubt, choose the option that keeps a human doctor in control and makes the AI's reasoning auditable.

---

## 5. Architecture

```
                ┌───────────────────────────────────────────────┐
                │  Next.js frontend (App Router, TS, Tailwind)  │
                │  - Reception: create patient, upload, verify  │
                │  - Doctor: Patient Snapshot (the wow screen)  │
                └───────────────┬───────────────────────────────┘
                                │ REST / websocket (auth: JWT)
                ┌───────────────▼───────────────────────────────┐
                │  FastAPI backend (Python)                     │
                │  - Auth & roles        - Patient/Doc APIs     │
                │  - Ingestion orchestrator                     │
                │  - RAG retrieval + summary generation         │
                └───┬──────────┬───────────┬──────────┬─────────┘
                    │          │           │          │
            ┌───────▼──┐  ┌────▼─────┐ ┌───▼──────┐ ┌─▼──────────────┐
            │ Postgres │  │ Object   │ │ LLM layer│ │ Async worker   │
            │+ pgvector│  │ storage  │ │(LiteLLM) │ │ (ingest pipe)  │
            │ (rel +   │  │(S3/R2)   │ │ swappable│ │                │
            │  vectors)│  │ raw files│ │ providers│ │                │
            └──────────┘  └──────────┘ └──────────┘ └────────────────┘
```

### Why these choices
- **Next.js frontend** — required; great for the polished doctor UI and live deploy (Vercel).
- **Python + FastAPI** — best ecosystem for RAG, OCR, embeddings, medical NLP.
- **Postgres + pgvector** — ONE store for relational data (patients, docs, users) *and* embeddings. Minimal infra for a hackathon.
- **Object storage (S3-compatible: Cloudflare R2 or Supabase Storage)** — raw uploaded files (images, PDFs, DICOM).
- **LiteLLM abstraction** — swap LLM/embedding providers via env (cloud now → self-hosted open model later). Honors our "swappable" decision.
- **Async worker** — ingestion (OCR/vision/embedding) is slow; never block the request. Start with FastAPI `BackgroundTasks`;
  upgrade to Celery/RQ + Redis if we need real queuing. Frontend polls or subscribes for status.

### AI hosting decision
Cloud APIs now, **behind an abstraction layer**, designed so a self-hosted open model (e.g. Llama / Qwen / MedGemma +
open embeddings via Ollama/vLLM) can drop in for the privacy-sensitive government deployment story. Never call a provider
SDK directly from feature code — always go through the LLM layer.

---

## 6. The two pipelines

### 6a. Ingestion pipeline (per uploaded item)
```
upload → store raw file → classify doc type → extract → structure → verify (human) → chunk → embed → index
```
- **Classify**: prescription | lab report | discharge summary | scan film | typed note | other.
- **Extract**:
  - Photos / handwriting / scanned docs → **vision-LLM-first** extraction (best on messy handwriting); traditional OCR
    (PaddleOCR/Tesseract) as fallback/cross-check.
  - Lab PDFs → structured value/trend extraction.
  - Scan films (X-ray/MRI/CT / DICOM) → metadata + embedded text + neutral caption only (NO pathology reading).
  - Typed entry → used directly.
- **Structure**: normalize into FHIR-shaped internal resources (Observation, MedicationRequest, etc.).
- **Verify**: proposed structured fields (esp. meds/doses/labs) surfaced for reception confirmation; low-confidence → `⚠`.
- **Chunk + embed + index**: store text chunks + embeddings in pgvector, each chunk carrying `patient_id`,
  `source_document_id`, doc type, date, and a citation anchor.

### 6b. Retrieval + summary pipeline (when doctor opens a patient)
```
retrieve longitudinal context → assemble → generate structured summary with citations → render snapshot
```
- Retrieve relevant chunks for the patient (meds, allergies, chronic conditions, recent labs/trends, past encounters, current complaint).
- Generate a **structured** summary — not a wall of text. Suggested sections:
  - **Current complaint / reason for visit**
  - **Active problems & chronic conditions**
  - **Allergies** (prominent, red)
  - **Current medications**
  - **Recent labs & trends** (with direction arrows)
  - **Past encounters / procedures** (timeline)
  - **⚠ Flags & things to verify** (missing data, unreadable docs, contradictions)
- Every item carries a citation chip → clicking opens the source document/region.
- The summary is generated in the selected language (English/Hindi/regional).

**Prefer citation-grounded generation:** the model may only use retrieved, cited content. If it can't cite, it omits.

---

## 7. Repository layout (target)

```
doc-mate/
├── README.md
├── docs/
│   └── PROJECT.md             # this file — project source of truth
├── frontend/                  # Next.js app (App Router, TS)
│   ├── app/
│   │   ├── (reception)/       # create patient, upload, verify extractions
│   │   └── (doctor)/          # patient snapshot
│   ├── components/
│   ├── lib/                   # api client, auth, i18n
│   └── ...
├── backend/                   # FastAPI service
│   ├── app/
│   │   ├── main.py
│   │   ├── api/               # routers: auth, patients, documents, ingest, summary
│   │   ├── core/              # config, security/JWT, deps
│   │   ├── db/                # models, migrations (Alembic), pgvector setup
│   │   ├── llm/               # LiteLLM wrapper — the ONLY place providers are called
│   │   ├── ingestion/         # classify, extract (vision/ocr), structure, chunk, embed
│   │   ├── rag/               # retrieval, prompt assembly, summary generation
│   │   ├── fhir/              # internal <-> FHIR-shaped mapping
│   │   └── workers/           # async ingestion tasks
│   └── tests/
└── infra/                     # docker-compose (postgres+pgvector, minio), deploy configs
```
> Layout is a target, not law. Create dirs as features land. Keep provider calls isolated in `backend/app/llm/`.

---

## 8. Tech stack (concrete)

**Frontend**
- Next.js (App Router) + TypeScript
- Tailwind CSS + shadcn/ui (fast path to a clean, professional clinical UI)
- TanStack Query for server state; lightweight client state only where needed
- i18n (next-intl or similar) for EN/HI/regional
- Deploy: Vercel

**Backend**
- Python 3.11+ + FastAPI + Uvicorn
- SQLAlchemy + Alembic (migrations); Pydantic v2 for schemas
- Postgres + `pgvector`
- LiteLLM for LLM + embedding calls (provider-agnostic)
- OCR fallback: PaddleOCR or Tesseract; PDF parsing: pymupdf; DICOM: pydicom
- Async: FastAPI BackgroundTasks → (Celery/RQ + Redis if needed)
- Deploy: container on Railway / Render / Fly.io

**Shared**
- Auth: JWT, roles `reception` / `doctor`
- Object storage: Cloudflare R2 or Supabase Storage (S3 API); MinIO locally
- Local dev: `docker-compose` for Postgres+pgvector and MinIO

> These are defaults chosen for hackathon speed + a credible privacy/scale story. Swapping any one should be a
> localized change, not a rewrite — keep boundaries clean (LLM layer, storage layer, DB layer).

---

## 9. Data model (FHIR-aligned, simplified)

Core entities (map onto FHIR resources noted in parentheses):
- **User** — id, name, role (`reception`|`doctor`), auth.
- **Patient** (`Patient`) — internal id, ABHA-style id, demographics, preferred language.
- **Encounter** (`Encounter`) — a visit; links to the patient and the docs uploaded for it.
- **Document** (`DocumentReference`) — one uploaded item: type, raw file ref (object storage), status
  (`uploaded|processing|extracted|verified|failed`), extracted text, confidence.
- **ClinicalItem** — normalized structured facts extracted from documents, each typed as one of:
  `Observation` (labs/vitals), `MedicationRequest`, `AllergyIntolerance`, `Condition`, `Procedure`.
  Every ClinicalItem references its source Document (for citations) and carries a confidence + `verified` flag.
- **Chunk** — text chunk + embedding (pgvector) + metadata (patient_id, document_id, doc type, date, citation anchor).
- **Summary** — generated snapshot for an encounter: structured sections + citations + language + generation metadata.

---

## 10. Coding conventions

- **Type everything.** TS strict on the frontend; Pydantic models + type hints on the backend.
- **Providers only in `backend/app/llm/`.** No LLM/embedding provider SDK imports outside that package.
- **No PHI in logs.** Never log patient content, file contents, or PII. Log ids and statuses only.
- **Citations are load-bearing.** Any summary-generation code must carry source refs end-to-end. A summary item without a
  resolvable source is a bug.
- **Fail loud in the pipeline.** A document that can't be processed becomes `status=failed` with a reason surfaced in the
  UI — never silently dropped.
- **Small, verifiable functions** for extraction/structuring; write tests for the FHIR mapping and citation plumbing.
- **Env-driven config** (`backend/app/core/config.py`), never hardcode keys/URLs. Provide `.env.example`.
- Match existing file style; keep comment density consistent with surrounding code.

---

## 11. Environment / secrets (via `.env`, never commit)

```
# LLM (LiteLLM-compatible)
LLM_PROVIDER=              # e.g. gemini | openai | ollama | vllm
LLM_MODEL_MULTIMODAL=      # model used for vision/OCR extraction
LLM_MODEL_REASONING=       # model used for summary generation
EMBEDDING_MODEL=
<PROVIDER>_API_KEY=

# Database
DATABASE_URL=postgresql+psycopg://...

# Object storage (S3 API)
S3_ENDPOINT= / S3_BUCKET= / S3_ACCESS_KEY= / S3_SECRET_KEY=

# Auth
JWT_SECRET= / JWT_EXPIRY=
```

---

## 12. Roadmap / build order

1. **Foundation** — repos, docker-compose (Postgres+pgvector, MinIO), FastAPI skeleton, Next.js skeleton, auth + roles.
2. **Data + upload** — Patient/Encounter/Document models, file upload to object storage, reception create-patient flow.
3. **Ingestion pipeline** — classify → extract (vision-LLM + OCR fallback) → structure → verify UI → chunk + embed + index.
4. **RAG summary** — retrieval + citation-grounded structured summary generation.
5. **Doctor Snapshot UI** — the high-polish, fast-read screen with citation chips. (Invest here — it's the wow moment.)
6. **Languages** — EN/HI/regional for summaries + input.
7. **Polish + deploy** — seed realistic synthetic data, deploy live, rehearse the demo, write the demo script in `docs/`.
8. **Roadmap slides (not built): ABDM/ABHA + FHIR sandbox integration, offline/PWA for rural clinics, self-hosted models.**

---

## 13. Glossary

| Term | Meaning |
|------|---------|
| SIH | Smart India Hackathon |
| RAG | Retrieval-Augmented Generation — retrieve relevant records, then generate grounded output |
| ABDM | Ayushman Bharat Digital Mission (India national digital health infra) |
| ABHA | 14-digit patient health ID under ABDM |
| FHIR | HL7 interoperability standard (R4) used by ABDM |
| HIP / HIU | Health Information Provider / User |
| OP | Outpatient (record created at intake) |
| PHI/PII | Protected Health / Personally Identifiable Information |
| DICOM | Standard format/metadata for medical imaging films |

---

## 14. Decisions locked (2026-08-24)

- Scope: polished demo/prototype, ABDM-ready but not certified.
- AI hosting: cloud APIs now, swappable to self-hosted via LiteLLM abstraction.
- Backend: Python + FastAPI. Frontend: Next.js.
- Inputs: all forms (typed, doc photos, scan films, lab PDFs).
- AI role: summarize + surface only — **no diagnosis**.
- Languages: English + Hindi + one regional.
- Auth: reception + doctor roles, simple JWT.
- Deploy: cloud-deployed, high-polish doctor UI.
