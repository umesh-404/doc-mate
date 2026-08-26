# Doc-mate — Backend

FastAPI service for Doc-mate: auth + roles, patient/document APIs, the ingestion
pipeline (classify → extract → structure → chunk → embed → index), hybrid RAG
retrieval, citation-grounded summary generation, and the clinical-safety,
interoperability, language, governance, evaluation, triage, consultation and
surveillance layers built on top.

See [`../docs/PROJECT.md`](../docs/PROJECT.md) for full project context —
**§15 is the authoritative list of all 40 routes**, and §16 states plainly which
parts are demo-grade.

- API base URL (local): `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Expected frontend origin (CORS): `http://localhost:3000`

Everything runs **offline by default**: with no `LLM_PROVIDER` set, the LLM
layer uses deterministic stubs for extraction, embeddings and summaries. No API
key is needed to run the app, the tests, the seeders or the smoke test.

## Requirements

- Python 3.11+
- PostgreSQL with the `pgvector` extension
- An S3-compatible object store (MinIO locally)

Postgres + MinIO come from `infra/docker-compose.yml`. The API does not open a
DB connection at startup, so it boots even before the database is up — requests
that touch the DB fail until it is reachable.

## Setup

```bash
cd backend

# 1. Virtual environment
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS/Linux:         source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env          # then edit as needed

# 4. Run database migrations (requires Postgres + pgvector reachable)
alembic upgrade head

# 5. Seed (all idempotent, all synthetic data)
python -m scripts.seed          # demo users
python -m scripts.seed_demo     # 5 showcase patients, docs, chunks, summaries
python -m scripts.seed_cohort   # ~100 background patients

# 6. Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Demo credentials (from the seed script)

| Role      | Email            | Password  |
|-----------|------------------|-----------|
| reception | `reception@demo` | `demo1234`|
| doctor    | `doctor@demo`    | `demo1234`|

## Scripts

| Command | What it does |
|---------|--------------|
| `python -m scripts.seed` | Demo users (reception + doctor). |
| `python -m scripts.seed_demo` | 5 showcase patients with documents, chunks, summaries, consent. |
| `python -m scripts.seed_cohort` | ~100 synthetic background patients (ABHA prefix `90-`). |
| `python -m scripts.e2e_smoke` | Real HTTP flow against a running backend: login → create patient → upload → ingest → verify → summary → citations. Exit 0 = pass. |
| `python -m scripts.run_eval` | Deterministic summary-quality benchmark (faithfulness / completeness / conciseness). `--misses` lists every omission and unsupported line. |
| `python -m scripts.test_llm` | Smoke-check the configured LLM provider (or the stub). |
| `pytest -q` | Full offline test suite — no DB, no network, no keys. |

## API surface

40 routes. `../docs/PROJECT.md` §15 has the complete table; the groups are:

| Area | Routes |
|------|--------|
| **Meta** | `GET /` · `GET /health` (unauthenticated) |
| **Auth** | `POST /auth/login` · `GET /auth/me` · `GET /users` (doctor) |
| **Patients** | `POST /patients` (reception) · `GET /patients` · `GET /patients/{id}` |
| **Documents** | `POST /documents` (reception, multipart) · `GET /documents?patient_id=` · `GET /documents/{id}` · `POST /documents/{id}/verify` (reception) |
| **Summary** | `POST /patients/{id}/summary` (202, background) · `GET /patients/{id}/summary` |
| **Search** | `GET /patients/{id}/search?q=&limit=` — semantic search over the patient's pgvector chunk index |
| **Language** | `GET /patients/{id}/summary/translated?lang=` · `…/summary/plain?lang=` |
| **Safety** | `GET /patients/{id}/interactions` |
| **Interop** | `GET /patients/{id}/fhir` · `GET /abha/lookup` (mock) · `GET /patients/{id}/codes` · `GET /coding/search` |
| **Voice** | `POST /voice/transcribe` |
| **Consult** | `POST/GET /patients/{id}/consult` · `GET /consult/{id}` · `POST /consult/{id}/verify` |
| **Governance** | `POST/DELETE/GET /patients/{id}/consent` · `GET /patients/{id}/audit` · `GET /audit/recent` |
| **Evaluation** | `POST /patients/{id}/summary/evaluate` · `GET …/summary/evaluation` · `GET /evaluation/benchmark` |
| **Triage** | `GET /triage/queue` · `GET /patients/{id}/triage` |
| **Surveillance** | `GET /surveillance/overview` · `GET /surveillance/trends` · `GET /surveillance/signals` |

### Auth notes

- `POST /auth/login` accepts **either** a JSON body `{"email","password"}`
  **or** an OAuth2 form (`username`=email, `password`).
- The JWT carries the user id (`sub`) and `role`. Send it as
  `Authorization: Bearer <token>`.
- Use `require_role(...)` (in `app/core/security.py`) to guard role-specific
  routes.

## Retrieval: the hybrid strategy

`app/rag/retrieval.py` carries the full rationale. In short:

- **Structured retrieval is exhaustive and stays the backbone.** Every
  `ClinicalItem` for the patient reaches summary generation. At OPD record size,
  completeness beats top-k — an omitted allergy is a safety failure, not a
  latency win.
- **Semantic retrieval adds the narrative** the structured items cannot hold
  (discharge-summary prose, notes), pulled from the `chunks` table by pgvector
  cosine similarity and passed to generation as additional *cited* context.
- **The threshold is explicit.** At or below `EXHAUSTIVE_CHUNK_THRESHOLD`
  (40 chunks) narrative retrieval returns every chunk; above it, top-`k`
  (`NARRATIVE_TOP_K` = 8) similarity search bounds the context for a large
  record.
- **Patient isolation is a SQL `WHERE`** on every path — a chunk from another
  patient can never be ranked, returned or cited (`tests/test_rag.py`).

## Governance: consent enforcement

Sensitive reads (`GET /patients/{id}`, `GET /documents/{id}`,
`GET /patients/{id}/summary`, `GET /patients/{id}/fhir`,
`GET /patients/{id}/search`) run through the consent gate in
`app/api/_consent.py`. Behaviour is set by `CONSENT_ENFORCEMENT`:

| Mode | Behaviour |
|------|-----------|
| `audit_only` | **Default.** Consent is evaluated and every denial is written to the audit trail, but the read is never blocked. Keeps the demo and `scripts.e2e_smoke` working end to end. |
| `enforce` | A denial returns `403 {"error":"consent_required", "reason":…}`. Callers pass `?break_glass_reason=emergency_care` to proceed — access is permitted and audit-flagged `break_glass=true` for retrospective review, because emergency care must never be blocked by paperwork. |
| `off` | Skip the check entirely (not recommended). |

Anything unrecognised falls back to `audit_only`. Both seeders grant explicit
consent for the patients they create, so the seeded demo works identically in
`enforce` mode.

Audit rows carry **ids, roles, enum actions and coded reasons only** — free-text
reasons are normalised against a closed vocabulary before storage, so patient
content can never reach the audit table.

## Migrations

The Alembic env reads `DATABASE_URL` from the environment (via
`app/core/config.py`). The initial migration enables `pgvector` before creating
tables, so it must run against a Postgres instance that has the extension
available.

```bash
alembic upgrade head            # apply
alembic downgrade -1            # roll back one
alembic revision --autogenerate -m "msg"   # needs a reachable DB
```

## Docker

```bash
docker build -t docmate-backend .
docker run --env-file .env -p 8000:8000 docmate-backend
```

## Project conventions

- **Providers only in `app/llm/`.** No LLM/embedding SDK imports elsewhere.
- **No PHI/PII in logs, URLs or audit rows.** Log ids and statuses only.
- **Citations are load-bearing.** A summary item without a resolvable source
  document is a bug; `_enforce_citations` drops it.
- **Fail loud in the pipeline.** An unprocessable document becomes
  `status=failed` with a reason surfaced in the UI — never silently dropped.
- **Env-driven config.** Never hardcode secrets or URLs; see `.env.example`.
