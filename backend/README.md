# Doc-mate — Backend

FastAPI service for Doc-mate. Provides auth, patient/document APIs, and the
foundations for the ingestion + RAG pipelines. See `../docs/PROJECT.md` for
full project context.

- API base URL (local): `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Expected frontend origin (CORS): `http://localhost:3000`

## Requirements

- Python 3.11+
- PostgreSQL with the `pgvector` extension
- An S3-compatible object store (MinIO locally)

Postgres + MinIO are expected via `infra/docker-compose` (see the `infra/`
directory). The API itself does not open a DB connection at startup, so it will
boot even before the database is up — requests that touch the DB will fail
until it is reachable.

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

# 5. Seed demo users (idempotent)
python -m scripts.seed

# 6. Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Demo credentials (from the seed script)

| Role      | Email            | Password  |
|-----------|------------------|-----------|
| reception | `reception@demo` | `demo1234`|
| doctor    | `doctor@demo`    | `demo1234`|

## Endpoints

| Method | Path                         | Auth / role        | Purpose                                  |
|--------|------------------------------|--------------------|------------------------------------------|
| GET    | `/`                          | none               | Service metadata                         |
| GET    | `/health`                    | none               | Health check → `{"status":"ok"}`         |
| POST   | `/auth/login`                | none (JSON or form)| Login → `{access_token, token_type, role}`|
| GET    | `/auth/me`                   | any authenticated  | Current user                             |
| POST   | `/patients`                  | reception          | Create a patient                         |
| GET    | `/patients`                  | any authenticated  | List patients                            |
| GET    | `/patients/{id}`             | any authenticated  | Get one patient                          |
| POST   | `/documents`                 | reception          | Upload a file (multipart) → Document     |
| GET    | `/documents?patient_id=...`  | any authenticated  | List a patient's documents               |
| GET    | `/users`                     | doctor             | List users                               |

### Auth notes

- `POST /auth/login` accepts **either** a JSON body `{"email","password"}`
  **or** an OAuth2 form (`username`=email, `password`).
- The JWT carries the user id (`sub`) and `role`. Send it as
  `Authorization: Bearer <token>`.
- Use `require_role(...)` (in `app/core/security.py`) to guard role-specific
  routes.

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
- **No PHI/PII in logs.** Log ids and statuses only.
- **Env-driven config.** Never hardcode secrets or URLs; see `.env.example`.
