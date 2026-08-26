# Doc-mate

> AI-assisted patient-context engine for high-volume government hospitals.
> Give the doctor everything about a patient in **under 1 minute**, so the 5-minute
> consultation is spent on diagnosis, not on reading paperwork.

This file is the source of truth for how we build Doc-mate. Read it fully before writing code.
Keep it updated as decisions change.

Companion docs: [`DEVELOPMENT.md`](DEVELOPMENT.md) (run it locally), [`LLM.md`](LLM.md) (the LLM layer,
stub vs real, self-hosting), [`DEPLOYMENT.md`](DEPLOYMENT.md) (production runbook),
[`DEMO.md`](DEMO.md) (demo-day script and seeded dataset).

Sections §1–§14 keep their original numbering — code comments and sibling docs cite them. Newer material is appended:
**§15 API surface** (every real endpoint) and **§16 status** (what is built vs what is demo-grade). Read §16 before
claiming anything about this system.

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
- Languages: **English + Hindi + Tamil + Telugu** (the chosen regional languages) for summaries and
  input handling.
- Cloud-deployable so judges can try it live. High-polish doctor UI.

Built on top of that core, and now also in scope (all implemented — see §6c):
clinical-safety checking, FHIR R4 export + ICD-11/NAMASTE coding, plain-language summaries,
voice intake, an ambient consultation scribe, consent + access audit, summary-quality evaluation,
OPD triage, and anonymized public-health surveillance.

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
- **DPDP Act 2023**: India's data-protection law. Consent must be explicit, purpose-bound, scoped and revocable;
  access must be accountable. This is what §6c's consent + audit layer is modelled on.
- **IDSP**: India's disease-surveillance programme — the reference point for the aggregate-only surveillance view.

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

The features built since these principles were written add four more guarantees, in the same spirit:

8. **The audit trail carries no patient content.** An `audit_logs` row holds ids, the actor's role, an enum action, a
   break-glass flag and a *coded* reason only. Caller-supplied free text is normalized to a code before it is stored, so
   a name, complaint or note can never reach the audit table even if a caller passes one. Writing an audit row must never
   break the request it is auditing.
9. **Triage suggests a review priority; it never diagnoses.** The score is deterministic, every reason is phrased as an
   observation plus a verification prompt (never "this patient has X", never "see this patient first"), every contributing
   fact is cited, and no vital, value or date is invented.
10. **The consultation scribe has no assessment section by construction.** Its keys are exactly
    `subjective | objective | plan | follow_up | flags` — there is no place for the system to record a conclusion of its
    own. Every line is a sentence lifted from the transcript; every proposed clinical item is a verbatim span and is
    `needs_verification=True` until a doctor accepts it.
11. **Surveillance is aggregate-only, with k-anonymity.** No patient id, name, ABHA id, document id or free text ever
    leaves that module. Every bucket below **K = 5** is returned as suppressed (never rounded), ages appear only as bands,
    and the outbreak trip-wire refuses to fire on a cell it would have had to suppress.

When in doubt, choose the option that keeps a human doctor in control and makes the AI's reasoning auditable.

---

## 5. Architecture

```
        ┌──────────────────────────────────────────────────────────────┐
        │  Next.js frontend (App Router, TS, Tailwind)                 │
        │  - Reception: create patient, upload, verify extractions     │
        │  - Doctor: Patient Snapshot (the wow screen)                 │
        │  - EN/HI/TE/TA switcher, light+dark theme, voice capture     │
        └───────────────────────────┬──────────────────────────────────┘
                                    │ REST (auth: JWT bearer)
        ┌───────────────────────────▼──────────────────────────────────┐
        │  FastAPI backend (Python)                                    │
        │                                                              │
        │  api/         auth · patients · documents · summaries ·      │
        │               users · safety · interop · language · voice ·  │
        │               governance · evaluation · triage · consult ·   │
        │               surveillance                                   │
        │                                                              │
        │  ingestion/   classify → extract → structure → chunk → embed │
        │  rag/         retrieval + citation-grounded summary          │
        │  safety/      grounding score · alerts · interaction checks  │
        │  fhir/  coding/   FHIR R4 bundles · ICD-11 / NAMASTE · ABHA  │
        │  language/ voice/ translation · plain language · speech      │
        │  consult/     ambient scribe (capture → draft → verify)      │
        │  governance/  consent + append-only access audit             │
        │  eval/ triage/ surveillance/  quality · queue · aggregates   │
        └───┬──────────┬───────────┬──────────┬────────────────────────┘
            │          │           │          │
    ┌───────▼──┐  ┌────▼─────┐ ┌───▼──────┐ ┌─▼──────────────┐
    │ Postgres │  │ Object   │ │ LLM layer│ │ Async worker   │
    │+ pgvector│  │ storage  │ │(LiteLLM) │ │ (ingest pipe,  │
    │ (rel +   │  │(S3/R2/   │ │ swappable│ │  Background-   │
    │  vectors)│  │ MinIO)   │ │ + stubs  │ │  Tasks)        │
    └──────────┘  └──────────┘ └──────────┘ └────────────────┘
```

### Why these choices
- **Next.js frontend** — required; great for the polished doctor UI and live deploy (Vercel).
- **Python + FastAPI** — best ecosystem for RAG, OCR, embeddings, medical NLP.
- **Postgres + pgvector** — ONE store for relational data (patients, docs, users) *and* embeddings. Minimal infra for a hackathon.
- **Object storage (S3-compatible: MinIO locally, Cloudflare R2 or Supabase Storage in cloud)** — raw uploaded files
  (images, PDFs) and captured consultation audio.
- **LiteLLM abstraction** — swap LLM/embedding providers via env (cloud now → self-hosted open model later). Honors our "swappable" decision.
- **Async worker** — ingestion (OCR/vision/embedding) is slow; never block the request. Currently FastAPI `BackgroundTasks`
  behind a narrow `enqueue_ingestion` seam, so Celery/RQ + Redis can replace it without touching routers. The frontend polls
  for status.
- **Offline-first everything.** Every capability has a deterministic path that needs no provider, no key and no network:
  stub extraction/summary/embeddings, glossary translation, bundled interaction and coding datasets, stub transcription.
  Real models are an env-var upgrade, never a prerequisite.

### AI hosting decision
Cloud APIs behind an abstraction layer, designed so a self-hosted open model (e.g. Llama / Qwen / MedGemma +
open embeddings via Ollama/vLLM) can drop in for the privacy-sensitive government deployment story. Never call a provider
SDK directly from feature code — always go through the LLM layer. **Stub mode is the default**: with no `LLM_PROVIDER`
and no key, the whole pipeline runs offline on deterministic synthetic output. See [`LLM.md`](LLM.md).

---

## 6. The pipelines

### 6a. Ingestion pipeline (per uploaded item)
```
upload → store raw file → classify doc type → extract → structure → verify (human) → chunk → embed → index
```
- **Classify**: prescription | lab report | discharge summary | scan film | typed note | other. Inferred from filename
  keywords, extension, then MIME type when the upload came in as `other`.
- **Extract** (via `app/llm/service.py`, which picks stub or provider):
  - Photos / handwriting / scanned docs → **vision-LLM-first** extraction in real mode; PDFs are rendered to page images
    with PyMuPDF, or read as text with pypdf.
  - Scan films (X-ray/MRI/CT) → metadata + embedded text + neutral caption only (NO pathology reading).
  - Typed entry → used directly.
  - In stub mode all of the above return deterministic, seeded synthetic output flagged `data.stub = True`.
- **Structure**: normalize into FHIR-shaped internal `ClinicalItem` rows (Observation, MedicationRequest,
  AllergyIntolerance, Condition, Procedure), each `verified=False` and citing its source document.
- **Verify**: proposed structured fields (esp. meds/doses/labs) surfaced for reception confirmation; low-confidence → `⚠`.
- **Chunk + embed + index**: store text chunks + embeddings in pgvector, each chunk carrying `patient_id`,
  `document_id`, doc type, date, and a citation anchor.
- **Fail loud**: any failure sets `status=failed` with the exception type/message (never document content) in
  `error_reason`, surfaced in the UI.

### 6b. Retrieval + summary pipeline (when doctor opens a patient)
```
retrieve longitudinal context → assemble → generate structured summary with citations
    → clinical-safety pass → persist → render snapshot
```
- Retrieve the patient's structured clinical facts, each carrying `document_id` + `citation_label`.
  *Today retrieval is exhaustive over a patient's `ClinicalItem` rows rather than a vector search — a patient's fact set is
  small enough to pass whole, and it guarantees nothing is dropped. Chunks and embeddings are written at ingest and are the
  seam for semantic retrieval when the record set grows.*
- Generate a **structured** summary — not a wall of text. The seven sections, always in this order:
  - **Current complaint / reason for visit** (`complaint`)
  - **Active problems & chronic conditions** (`problems`)
  - **Allergies** (`allergies` — prominent, red)
  - **Current medications** (`medications`)
  - **Recent labs & trends** (`labs`, with direction arrows)
  - **Past encounters / procedures** (`encounters`)
  - **⚠ Flags & things to verify** (`flags` — missing data, unreadable docs, contradictions)
- Every item carries a citation chip → clicking opens the source document. Citations are enforced twice: in the provider
  path and again in the RAG layer. A non-`flags` item whose citations do not resolve to a real document id is dropped.
- The summary is persisted with its generation metadata (mode, fact count, grounding, alerts) and generated in the
  patient's preferred language.

**Prefer citation-grounded generation:** the model may only use retrieved, cited content. If it can't cite, it omits.

### 6c. What runs alongside those two

Each of these is a package under `backend/app/`, deterministic and offline by default.

- **Clinical-safety pass** (`safety/`) — runs on every generated summary. `grounding.py` grades each summary line against
  the text of the source it cites (content-token overlap plus exact numeric matching) and returns a 0–1 grounding score;
  it is a heuristic signal, not an NLI model, tuned to catch lines that introduce entities or numbers absent from the
  source. `interactions.py` checks drug–drug interactions and drug–allergy conflicts against a small bundled reference
  dataset (`safety/data/interactions.json`) — no external API, and only *verified* items are considered, so an unconfirmed
  OCR extraction never drives a flag. `alerts.py` assembles the results into neutral, cited alerts
  (`allergy | interaction | abnormal_lab | missing_data`, at `critical | warning | info`).
- **Interoperability** (`fhir/`, `coding/`) — `builder.py` composes a FHIR R4 collection Bundle for a patient at request
  time from existing rows, with stable derived resource ids and working `{ResourceType}/{id}` references. The output is
  schema-plausible R4, **not** validator-clean: ABDM India-profile extensions are omitted and terminology bindings are
  light. `coding/service.py` maps clinical labels onto bundled **ICD-11** and **NAMASTE** entries offline, never
  fabricating a code — no match returns an empty list, and codings are attached to FHIR resources only when they resolve.
  `fhir/abha.py` is a **mock** ABHA identity resolver: it returns a seeded, deterministic synthetic identity flagged
  `source="mock"`. It is not NHA integration.
- **Multilingual + plain language** (`language/`) — translates the structured snapshot into **en / hi / te / ta**.
  Default
  (stub) mode uses bundled glossary packs (`language/data/*.json`) for section titles and common clinical phrases —
  that caveat applies to Telugu exactly as it does to Hindi and Tamil;
  real mode routes through `app/llm`. Either way a clinical value is never altered: every translated string is checked
  against its source and, if a numeric or dose token went missing, the **original** text is kept. `simplify.py` produces a
  short patient-facing plain-language narrative from the same facts — still no diagnosis, still no advice.
- **Voice intake** (`voice/`) — transcribes spoken intake audio. Real mode uses `faster-whisper` **on-device** (an optional,
  commented-out dependency) so audio never leaves the premises; with the library or model absent it returns a
  deterministic stub transcription and flags `stub: true`. It never raises for a missing model.
- **Ambient consultation scribe** (`consult/`) — capture audio and/or typed text → transcript → draft note → doctor
  verification. Structuring is pure and deterministic: sentences are lifted from the transcript, proposed clinical items
  are verbatim regex-matched spans, hedged or inaudible speech is flagged `⚠ needs verification`, and there is **no
  assessment section**. Nothing reaches the patient's record until the doctor verifies the note, at which point accepted
  items become real `ClinicalItem` rows cited to a consultation document.
- **Consent + access audit** (`governance/`) — DPDP-aligned consent that is explicit, scoped
  (`full_record | summary_only | documents_only`), purpose-bound, expirable and revocable in real time, plus an append-only
  audit trail of who accessed what and why. A **break-glass** path exists so emergency care is never blocked by paperwork:
  access without consent requires an explicit reason and writes an audit row flagged `break_glass=True` for review.
  *Status: consent records, revocation, the audit trail and enforcement are all live. `consent_gate(...)` is attached to
  the clinically sensitive reads (patient detail, document detail, summary, FHIR export, record search). Enforcement is
  controlled by `CONSENT_ENFORCEMENT`: `audit_only` (the default — evaluate and audit every decision, never block),
  `enforce` (403 unless consent is active or a `break_glass_reason` is supplied, which is audit-flagged), or `off`.
  An unrecognised value fails safe to `audit_only`, never to `off`. The default is deliberate: the seeded demo and the
  end-to-end smoke test create patients through the API without granting consent first.*
- **Quality evaluation** (`eval/`) — deterministic, offline scoring of a generated summary on **faithfulness**
  (fraction of non-`flags` items supported by their cited source, delegated to the grounding check), **completeness**
  (fraction of the patient's safety-critical facts actually surfaced) and **conciseness**, plus an overall score. Every
  score comes with a `details` dict explaining exactly how it was reached, and results persist as `summary_evals` rows.
  A CLI report is available via `python -m scripts.run_eval`.
- **OPD triage** (`triage/`) — turns a patient's already-ingested facts into a **suggested review priority**
  (`emergency | urgent | routine`), a 0–100 score and cited reasons, and builds the waiting queue in both arrival order and
  suggested order. Computed at request time from existing tables — no new columns, so a suggestion can never go stale or
  become a stored clinical assertion. Every weight and threshold is a module-level constant. `waiting_since` is a
  documented proxy (latest encounter time, else its row-insert time, else patient creation), not a real check-in timestamp.
- **Public-health surveillance** (`surveillance/`) — anonymized, aggregate-only views over the whole record set: condition
  prevalence, age-band/sex cells, language mix, data-quality counts, per-week/month trends for one condition, and a
  documented naive outbreak trip-wire. Small-cell suppression at **K = 5** is applied at every level, ages are banded, and
  the query string is normalized through the offline coder rather than echoed back. Demo-grade statistics that always
  require human epidemiological review.

---

## 7. Repository layout (actual)

```
doc-mate/
├── README.md
├── .env.example                  # project-wide reference for every env var
├── .env.production.example
├── render.yaml                   # Render blueprint (backend)
├── deploy/fly.toml               # Fly.io alternative
├── .github/workflows/ci.yml
├── docs/
│   ├── PROJECT.md                # this file — project source of truth
│   ├── DEVELOPMENT.md            # local quickstart
│   ├── LLM.md                    # LLM layer, stub vs real, self-hosting
│   ├── DEPLOYMENT.md             # production runbook
│   └── DEMO.md                   # demo-day script + seeded dataset
├── frontend/                     # Next.js app (App Router, TS)
│   ├── app/
│   │   ├── (reception)/reception/patients/{,new,[id]}
│   │   ├── (doctor)/doctor/patients/{,[id]}
│   │   ├── layout.tsx · page.tsx · globals.css
│   ├── components/               # AppHeader, UploadDropzone, VoiceCapture,
│   │   ├── snapshot/             #   PatientSnapshotView, AlertsBanner,
│   │   │                         #   GroundingBadge, MedicationSafetyCard,
│   │   │                         #   PlainLanguagePanel, Sparkline, …
│   │   ├── reception/            #   DocumentVerifyCard
│   │   └── ui/                   #   Button, Card, Badge, Input, Section, …
│   └── lib/                      # api client, auth, TanStack Query hooks,
│                                 # i18n dictionaries, theme, shortcuts, types
├── backend/                      # FastAPI service
│   ├── app/
│   │   ├── main.py               # mounts every router
│   │   ├── api/                  # auth, patients, documents, summaries, users,
│   │   │                         # safety, interop, language, voice,
│   │   │                         # governance, evaluation, triage, consult,
│   │   │                         # surveillance
│   │   ├── schemas/              # Pydantic v2 request/response models
│   │   ├── core/                 # config, security/JWT, S3 storage client
│   │   ├── db/                   # Base, session, ORM models
│   │   ├── llm/                  # service (public API) · stub · provider
│   │   │                         # — the ONLY place providers are called
│   │   ├── ingestion/            # classify, extract, structure, chunk, embed
│   │   ├── rag/                  # retrieval + summary generation
│   │   ├── safety/               # grounding, interactions, alerts (+ data/)
│   │   ├── fhir/                 # builder, mapping, mock ABHA
│   │   ├── coding/               # ICD-11 / NAMASTE lookup (+ data/)
│   │   ├── language/             # translate, simplify, glossary (+ data/)
│   │   ├── voice/                # transcribe (faster-whisper or stub)
│   │   ├── consult/              # scribe pipeline + deterministic structuring
│   │   ├── governance/           # consent, audit
│   │   ├── eval/                 # metrics, runner
│   │   ├── triage/               # scoring, queue
│   │   ├── surveillance/         # aggregate (k-anonymity)
│   │   └── workers/              # async ingestion tasks
│   ├── alembic/versions/         # 0001 initial · 0002 patient fields /
│   │                             # nullable summary encounter · 0003 governance,
│   │                             # consult notes, evals
│   ├── scripts/                  # seed, seed_demo, seed_cohort,
│   │                             # e2e_smoke, run_eval, test_llm
│   ├── tests/                    # llm_stub, safety, interop, language_voice,
│   │                             # governance, eval, triage, consult, surveillance
│   └── Dockerfile · requirements.txt · alembic.ini
└── infra/                        # docker-compose (postgres+pgvector, minio)
```
> Keep provider calls isolated in `backend/app/llm/`. Each capability is its own package with its data bundled beside it.

---

## 8. Tech stack (concrete)

**Frontend**
- Next.js 14 (App Router) + TypeScript (strict)
- Tailwind CSS with a small hand-rolled UI kit in `components/ui/` (Button, Card, Badge, Input, Section, Skeleton,
  States) — no component library dependency; `lucide-react` for icons, `clsx` + `tailwind-merge` for class composition
- TanStack Query for server state (including polling document status); React context for auth, theme and locale
- i18n via bundled dictionaries + a `localStorage`-backed context (`lib/i18n/`) for EN/HI/TE/TA — no i18n framework
  dependency
- Deploy target: Vercel

**Backend**
- Python 3.11+ + FastAPI + Uvicorn
- SQLAlchemy 2.0 + Alembic (migrations); Pydantic v2 + pydantic-settings for schemas/config
- Postgres + `pgvector` (psycopg v3 driver)
- LiteLLM for LLM + embedding calls (provider-agnostic), with deterministic offline stubs as the default path
- PDF handling: PyMuPDF (render pages to images for multimodal extraction) with pypdf as the text fallback; Pillow for images
- Optional on-device speech-to-text: `faster-whisper` (commented out in `requirements.txt`; stub transcription otherwise)
- Async: FastAPI `BackgroundTasks` behind a narrow seam → (Celery/RQ + Redis if needed)
- Tests: pytest (`backend/tests/`), all offline
- Deploy: container on Render (`render.yaml`) or Fly.io (`deploy/fly.toml`)

**Not currently used** (contrary to earlier plans, kept here so nobody assumes otherwise): no PaddleOCR/Tesseract OCR
fallback — extraction is vision-LLM-first with stub fallback; no `pydicom` / DICOM parsing — scan films are handled as
images; no websockets — the frontend polls.

**Shared**
- Auth: JWT, roles `reception` / `doctor`
- Object storage: MinIO locally; Cloudflare R2 or Supabase Storage (S3 API) in cloud
- Local dev: `docker-compose` for Postgres+pgvector and MinIO (see [`DEVELOPMENT.md`](DEVELOPMENT.md))

> These are defaults chosen for hackathon speed + a credible privacy/scale story. Swapping any one should be a
> localized change, not a rewrite — keep boundaries clean (LLM layer, storage layer, DB layer).

---

## 9. Data model (FHIR-aligned, simplified)

Core entities (map onto FHIR resources noted in parentheses). All primary keys are UUIDs so ids are opaque and
non-enumerable.

- **User** — id, email, name, role (`reception`|`doctor`), hashed password, active flag.
- **Patient** (`Patient`) — internal id, ABHA-style id, name, sex/age (plus gender/DOB for richer FHIR demographics),
  phone, preferred language, free-form `demographics` JSON.
- **Encounter** (`Encounter`) — a visit; reason, status, `occurred_at`; links to the patient and its documents/summaries.
- **Document** (`DocumentReference`) — one uploaded item: type, storage key, filename/content type/size, status
  (`uploaded|processing|extracted|verified|failed`), extracted text, confidence, `error_reason`.
- **ClinicalItem** — normalized structured facts extracted from documents, each typed as one of:
  `observation` (labs/vitals), `medication`, `allergy`, `condition`, `procedure`.
  Every ClinicalItem references its source Document (for citations) and carries a confidence + `verified` flag.
- **Chunk** — text chunk + embedding (pgvector, width `EMBEDDING_DIM`) + metadata (patient_id, document_id, doc type,
  date, citation anchor).
- **Summary** — generated snapshot: structured sections + citations + language + `generation_metadata`
  (mode, fact count, grounding score, alerts). Patient-scoped; the encounter link is optional.
- **Consent** — patient_id, scope (`full_record|summary_only|documents_only`), status (`granted|revoked|expired`),
  purpose, granting user, granted/revoked/expiry timestamps.
- **AuditLog** — append-only: actor user + role, action enum, resource type/id, patient_id, `break_glass` flag, coded
  reason. **Never carries patient content.**
- **ConsultNote** — patient/encounter/author, status (`captured|transcribing|drafted|verified|failed`), language,
  audio storage key, transcript, structured `sections` (no assessment key), confidence, `error_reason`.
- **SummaryEval** — per-summary faithfulness / completeness / conciseness / overall scores, the `method` that produced
  them, and a `details` payload.

Migrations: `0001` initial schema (+ `CREATE EXTENSION vector`), `0002` patient fields and nullable summary encounter,
`0003` governance, consult notes and evals.

---

## 10. Coding conventions

- **Type everything.** TS strict on the frontend; Pydantic models + type hints on the backend.
- **Providers only in `backend/app/llm/`.** No LLM/embedding provider SDK imports outside that package.
- **No PHI in logs.** Never log patient content, file contents, or PII. Log ids, statuses and exception *types* only.
- **Citations are load-bearing.** Any summary-generation code must carry source refs end-to-end. A summary item without a
  resolvable source is a bug.
- **Fail loud in the pipeline.** A document that can't be processed becomes `status=failed` with a reason surfaced in the
  UI — never silently dropped.
- **Deterministic by default.** Every feature must have an offline path that needs no key and no network, and it must
  produce the same output for the same input. Real-model paths degrade to it rather than failing.
- **Data lives beside its module** (`safety/data/`, `coding/data/`, `language/data/`) — bundled, versioned, no network.
- **Small, verifiable functions** for extraction/structuring; write tests for the FHIR mapping and citation plumbing.
- **Env-driven config** (`backend/app/core/config.py`), never hardcode keys/URLs. Provide `.env.example`.
- Match existing file style; keep comment density consistent with surrounding code.

---

## 11. Environment / secrets (via `.env`, never commit)

Canonical list; see [`../.env.example`](../.env.example) (project-wide reference), `backend/.env.example` (what the
backend actually loads) and `frontend/.env.example`.

```
# App
APP_NAME=Doc-mate
ENVIRONMENT=local
CORS_ORIGINS=http://localhost:3000   # comma-separated

# Database
DATABASE_URL=postgresql+psycopg://...

# Auth
JWT_SECRET= / JWT_ALGORITHM=HS256 / JWT_EXPIRY=1440    # minutes

# Object storage (S3 API)
S3_ENDPOINT= / S3_BUCKET= / S3_ACCESS_KEY= / S3_SECRET_KEY= / S3_REGION=

# LLM (LiteLLM-compatible). Leave LLM_PROVIDER empty for offline stub mode.
LLM_PROVIDER=              # e.g. gemini | openai | ollama | vllm | stub
LLM_MODEL_MULTIMODAL=      # model used for vision/OCR extraction
LLM_MODEL_REASONING=       # model used for summary generation / translation
EMBEDDING_MODEL=
EMBEDDING_DIM=1536         # MUST match the model output and the pgvector column
<PROVIDER>_API_KEY=        # e.g. GEMINI_API_KEY; absent ⇒ stub mode

# Frontend (Vercel / .env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Deployment also uses `WEB_CONCURRENCY` on the backend host — see [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## 12. Roadmap / build order

Honest status per capability lives in §16; this is the build order.

Done:

1. ✅ **Foundation** — docker-compose (Postgres+pgvector, MinIO), FastAPI skeleton, Next.js skeleton, auth + roles.
2. ✅ **Data + upload** — Patient/Encounter/Document models, upload to object storage, reception create-patient flow.
3. ✅ **Ingestion pipeline** — classify → extract → structure → verify UI → chunk + embed + index.
4. ✅ **RAG summary** — retrieval + citation-grounded structured summary generation, with citation enforcement.
5. ✅ **Doctor Snapshot UI** — the fast-read screen with citation chips, alerts, grounding badge and lab sparklines.
6. ✅ **Languages** — EN/HI/TE/TA snapshot translation + plain-language narrative (glossary-based by default).
7. ✅ **Clinical safety** — grounding score, neutral alerts, offline drug-interaction and allergy checking.
8. ✅ **Interoperability** — FHIR R4 bundle export, ICD-11/NAMASTE coding, mock ABHA lookup.
9. ✅ **Governance** — consent records + real-time revocation, PHI-free append-only access audit, break-glass path.
10. ✅ **Quality, triage, surveillance, scribe** — deterministic summary evaluation, OPD triage queue, k-anonymised
    aggregate surveillance, ambient consultation scribe.
11. ✅ **Real LLM path + deploy artifacts** — LiteLLM provider path, Dockerfile, Render/Fly/Vercel configs, CI.

Ahead:

12. **Deploy live** — provision managed Postgres + object storage, ship the backend and frontend, wire CORS
    ([`DEPLOYMENT.md`](DEPLOYMENT.md) has the runbook). Not done yet.
13. **Run with a real provider** — set `LLM_PROVIDER` + key, validate extraction on genuinely messy scans/handwriting,
    tune `EMBEDDING_DIM` and the pgvector column together.
14. **Make consent enforcement binding** — the gate is wired and working; production should run
    `CONSENT_ENFORCEMENT=enforce` and surface the break-glass prompt in the UI.
15. **Real embeddings for semantic retrieval** — the pgvector query path, patient isolation and citations are live, but
    stub embeddings are deterministic hashes, so ranking only becomes meaningful with a provider.
16. **Frontend for the API-only features** — triage queue, consent + audit panel, consult scribe, surveillance dashboard,
    and patient record search.
17. **Real speech** — ship `faster-whisper` on-device and validate Hindi, Tamil and Telugu intake audio.
18. **Roadmap slides (not built):** ABDM/ABHA + FHIR sandbox integration and HIP/HIU consent flows, offline/PWA for rural
    clinics, self-hosted MedGemma-class models on-prem, real terminology services, queuing (Celery/RQ + Redis).

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
| DPDP Act | Digital Personal Data Protection Act 2023 (India) — consent + accountability rules |
| IDSP | Integrated Disease Surveillance Programme (India) |
| k-anonymity | Suppressing any aggregate bucket smaller than K (here K=5) so individuals can't be re-identified |
| Break-glass | Emergency access without consent, permitted only with a reason and always audited |
| OP | Outpatient (record created at intake) |
| PHI/PII | Protected Health / Personally Identifiable Information |
| DICOM | Standard format/metadata for medical imaging films |

---

## 14. Decisions locked

### 2026-08-24

- Scope: polished demo/prototype, ABDM-ready but not certified.
- AI hosting: cloud APIs now, swappable to self-hosted via LiteLLM abstraction.
- Backend: Python + FastAPI. Frontend: Next.js.
- Inputs: all forms (typed, doc photos, scan films, lab PDFs).
- AI role: summarize + surface only — **no diagnosis**.
- Languages: English + Hindi + one regional.
- Auth: reception + doctor roles, simple JWT.
- Deploy: cloud-deployed, high-polish doctor UI.

### 2026-08-26

- **Regional language is Tamil** (`ta`), alongside `en` and `hi`.
- **Stub mode is the default everywhere**, not a fallback. Every capability ships a deterministic, offline, key-free path;
  real models are an env-var upgrade. This is what makes the demo run on venue wifi and the tests run in CI.
- **Bundled reference data over external services** — drug interactions, ICD-11/NAMASTE, translation glossaries all live
  beside their module. No terminology or interaction API is called at runtime.
- **The safety pass is part of summary generation**, not an optional add-on: grounding score + alerts are computed on
  every summary and persisted in `generation_metadata` (no new columns).
- **Governance is DPDP-shaped**: explicit, scoped, revocable consent; append-only, PHI-free audit; break-glass with a
  mandatory reason.
- **Triage, surveillance and the consult scribe never conclude.** Triage suggests priority with cited observations;
  surveillance emits aggregates with K=5 suppression; the scribe has no assessment section by construction.
- **No new tables for derived views.** Triage and FHIR bundles are computed at request time so a suggestion or export can
  never become a stale stored clinical assertion.
- **Frontend keeps its dependency surface small**: hand-rolled Tailwind UI kit and a bundled i18n context instead of a
  component library and an i18n framework.
- **UI is deliberately behind the API** for triage, surveillance, consult, governance and evaluation — the contracts are
  frozen and tested first.

### 2026-08-26 (language set widened, same day)

- **Telugu (`te`) is a first-class fourth language**, alongside `en`, `hi` and `ta`. Andhra Pradesh and Telangana are
  among the largest catchments a southern district hospital serves, and the language layer was already list-driven —
  a fourth glossary pack and a fourth switcher entry, not a redesign. The "one regional language" decision above
  stands as written; this widens it rather than replacing it.
- **The stub-mode caveat is unchanged and applies to Telugu identically**: glossary-based section titles and common
  clinical phrases offline, full sentence-level translation only in real mode. Clinical values, doses and citations
  are preserved verbatim in Telugu by the same check that protects Hindi and Tamil.
- **Seed data carries the language too**, so the claim is demonstrable rather than declared: a Telugu showcase patient
  in `scripts.seed_demo` and a Telugu share of the background cohort large enough to clear K=5 in the surveillance
  language mix.

---

## 15. API surface

All routes require a JWT bearer token except `/`, `/health` and `/auth/login`. Role guards are noted where they apply.

| Area | Method + path | Notes |
|------|---------------|-------|
| **Meta** | `GET /` · `GET /health` | service metadata; `{"status":"ok"}` |
| **Auth** | `POST /auth/login` | JSON `{email,password}` **or** OAuth2 form; returns `{access_token, token_type, role}` |
| | `GET /auth/me` | current user |
| | `GET /users` | **doctor** only |
| **Patients** | `POST /patients` | **reception** only |
| | `GET /patients` · `GET /patients/{id}` | list (limit/offset) · one (audited) |
| **Documents** | `POST /documents` | **reception** only; multipart; kicks off background ingestion |
| | `GET /documents?patient_id=…` | a patient's documents |
| | `GET /documents/{id}` | detail + proposed clinical items (audited) |
| | `POST /documents/{id}/verify` | human-in-the-loop confirmation of items (audited) |
| **Summary** | `POST /patients/{id}/summary` | 202; generates in the background (audited) |
| | `GET /patients/{id}/summary` | latest snapshot incl. grounding + alerts (audited) |
| **Language** | `GET /patients/{id}/summary/translated?lang=` | `en \| hi \| te \| ta`; values/citations untouched |
| | `GET /patients/{id}/summary/plain?lang=` | patient-friendly narrative |
| **Safety** | `GET /patients/{id}/interactions` | drug–drug + drug–allergy report over *verified* items |
| **Search** | `POST /patients/{id}/search` | semantic search over that patient's chunks. POST, not GET: the query is patient content and must not reach a URL or access log (§4.6) |
| **Interop** | `GET /patients/{id}/fhir` | FHIR R4 collection Bundle |
| | `GET /abha/lookup?abha_id=` | **mock** resolver (demo, not NHA) |
| | `GET /patients/{id}/codes` | ICD-11 / NAMASTE codes for the patient's items |
| | `GET /coding/search?term=&system=` | free-text search over the bundled code lists |
| **Voice** | `POST /voice/transcribe` | multipart audio → `{text, lang, confidence, stub}` |
| **Consult** | `POST /patients/{id}/consult` | audio and/or text → drafted note (inline) |
| | `GET /patients/{id}/consult` · `GET /consult/{note_id}` | list · detail |
| | `POST /consult/{note_id}/verify` | the human gate; writes accepted items into the record |
| **Governance** | `POST /patients/{id}/consent` · `DELETE …` · `GET …` | grant · revoke (real time) · latest (200 with `null` if never recorded) |
| | `GET /patients/{id}/audit` · `GET /audit/recent` | access history; contains no patient content |
| **Evaluation** | `POST /patients/{id}/summary/evaluate` | score + persist the latest summary |
| | `GET /patients/{id}/summary/evaluation` | latest stored scores |
| | `GET /evaluation/benchmark` | sweep across every patient's latest summary |
| **Triage** | `GET /triage/queue?limit=` | arrival order + suggested review order |
| | `GET /patients/{id}/triage` | one patient's suggested priority + cited reasons |
| **Surveillance** | `GET /surveillance/overview` | k-anonymised prevalence, age/sex bands, languages, data quality |
| | `GET /surveillance/trends?condition=&bucket=` | `week \| month` |
| | `GET /surveillance/signals?bucket=` | naive outbreak trip-wire |

Interactive docs: `/docs` on the running backend.

---

## 16. Status: what is built, what is demo-grade

**Built and working end-to-end (offline, no keys):** auth + roles; patient and document CRUD; upload to object storage;
background ingestion (classify → extract → structure → chunk → embed → index); reception verification; citation-grounded
summary generation with the clinical-safety pass; snapshot UI with citation chips, alerts, grounding badge, medication
safety card, plain-language panel, sparklines, EN/HI/TE/TA switching and light/dark theme; FHIR export; ICD-11/NAMASTE
coding; translation + simplification; voice intake endpoint; consultation scribe; consent + audit; quality evaluation;
triage; surveillance. `backend/tests/` covers safety, interop, language/voice, governance, eval, triage, consult and
surveillance, all offline; `scripts/e2e_smoke.py` exercises the real HTTP flow against a running backend.

**Demo / synthetic / stubbed — say so out loud:**

| Thing | Reality |
|-------|---------|
| Extraction, summary, embeddings | Real LLM path is fully coded, but **stub mode is the default** and runs unless `LLM_PROVIDER` *and* its API key are both set. Stub output is deterministic synthetic data flagged `data.stub = True` — never real clinical reading. |
| Voice transcription | Stubbed unless `faster-whisper` is installed and a model loads; the stub returns a canned transcript and flags `stub: true`. |
| ABHA lookup | **Mock.** Deterministic synthetic identity, `source="mock"`. No NHA/ABDM integration, no real ABHA verification. |
| FHIR output | Schema-plausible R4 (correct `resourceType`, working references). **Not validator-clean**: no ABDM India-profile extensions, light terminology binding. |
| ICD-11 / NAMASTE | Small bundled code lists covering the demo vocabulary, not the full terminologies. |
| Translation | Glossary-based in stub mode (section titles + common phrases) for every language, Telugu included. Full sentence-level MT needs real mode. |
| Consent enforcement | Wired to the sensitive reads and fully working, but shipped in `audit_only` mode by default so the seeded demo and smoke test are not blocked. Flip `CONSENT_ENFORCEMENT=enforce` to make it binding. |
| Retrieval | Hybrid: exhaustive over structured clinical items (completeness beats top-k at OPD record size), plus pgvector similarity over narrative chunks above the threshold. In stub mode embeddings are deterministic hashes, so similarity *ranking* is not meaningful offline — the plumbing, isolation and citations are real, the semantics need a provider. |
| Grounding / eval scores | Deterministic lexical + numeric heuristics, not NLI or LLM-judge. Defensible and auditable, but not state of the art. |
| Surveillance signals | A documented naive trip-wire over aggregated counts. Demo-grade statistics requiring human review. |
| Patient data | 100% synthetic. `scripts.seed_demo` (6 showcase patients, spanning en/hi/te/ta) and `scripts.seed_cohort` (~100 background patients on an uneven en 48 / hi 27 / te 14 / ta 11 mix) — see [`DEMO.md`](DEMO.md). |
| Deployment | Deploy artifacts exist (`render.yaml`, `deploy/fly.toml`, Dockerfile, `vercel.json`) and CI runs, but **the system is not currently deployed** to a live URL. |
| Frontend coverage | The reception and doctor flows are built. Triage, surveillance, consult, consent/audit and evaluation are **API-only so far** — no UI yet. |

**Production-ready in shape, not in certification:** the architecture, data model, safety guarantees and privacy
posture are what a real deployment would use. Certification (ABDM), real terminology services, real ABHA and a clinical
validation study are not part of this build.
