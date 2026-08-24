# Deployment — production runbook

How to take Doc-mate from this repo to a live URL judges can try. Read
[`PROJECT.md`](PROJECT.md) for architecture and [`DEVELOPMENT.md`](DEVELOPMENT.md)
for local dev first.

## Target topology

| Layer            | Where it runs                                   |
|------------------|-------------------------------------------------|
| Frontend (Next.js) | **Vercel**                                    |
| Backend (FastAPI)  | **Render** (Docker container) — primary; Fly.io alternative in [`../deploy/fly.toml`](../deploy/fly.toml) |
| Database         | Managed **Postgres + pgvector** (Neon / Supabase / Render) |
| Object storage   | **S3-compatible** — Cloudflare R2 or Supabase Storage |
| LLM              | Optional. Empty provider = deterministic **stub mode**, no key |

Everything is configured through environment variables — no secrets are baked
into any image or committed to the repo.

---

## What secrets you must provide

You supply these yourself; they are never in the repo. Values are set in the
host dashboards (Render/Fly for backend, Vercel for frontend).

| Secret | Used for | How to get it |
|--------|----------|---------------|
| `DATABASE_URL` | Postgres connection | From Neon/Supabase/Render. Must start with `postgresql+psycopg://` |
| `JWT_SECRET` | Signing auth tokens | Generate: `openssl rand -hex 32` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Object storage auth | From R2 / Supabase Storage API tokens |
| `S3_ENDPOINT` / `S3_BUCKET` | Object storage location | Your R2/Supabase endpoint + bucket name |
| `<PROVIDER>_API_KEY` *(optional)* | Real LLM calls | Only if `LLM_PROVIDER` is set (e.g. `OPENAI_API_KEY`). **Skip for stub mode.** |

> **Stub mode:** leave `LLM_PROVIDER` empty and the entire ingestion/summary
> pipeline runs offline with deterministic synthetic output — no LLM key
> needed. This is the recommended default for the SIH demo.

---

## Full backend env var list (names only)

Set on the backend host (Render/Fly). See [`../.env.production.example`](../.env.production.example).

```
APP_NAME
ENVIRONMENT
WEB_CONCURRENCY
CORS_ORIGINS            # must include your Vercel URL(s)
DATABASE_URL            # secret; postgresql+psycopg://...
JWT_SECRET              # secret
JWT_ALGORITHM
JWT_EXPIRY
S3_ENDPOINT             # secret-ish
S3_BUCKET
S3_ACCESS_KEY           # secret
S3_SECRET_KEY           # secret
S3_REGION
LLM_PROVIDER            # empty = stub mode
LLM_MODEL_MULTIMODAL    # only if using a real provider
LLM_MODEL_REASONING     # only if using a real provider
EMBEDDING_MODEL         # only if using a real provider
EMBEDDING_DIM
<PROVIDER>_API_KEY      # secret; only if LLM_PROVIDER is set
```

Frontend (set on Vercel): `NEXT_PUBLIC_API_URL`.

---

## Deploy order (do these in sequence)

### 1. Provision managed Postgres (with pgvector)

Recommended: **Neon** or **Supabase** (both offer pgvector; Render Postgres
also works). pgvector must be available on the instance.

- Create the database and copy its connection string.
- Rewrite the prefix to the SQLAlchemy/psycopg driver form:
  `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME`
- You do **not** need to run `CREATE EXTENSION vector` by hand — Alembic
  migration `0001` runs `CREATE EXTENSION IF NOT EXISTS vector` for you in
  step 4. (On Supabase you may enable the `vector` extension from the
  dashboard too; on Neon/Render the migration handles it.)

### 2. Provision object storage + bucket

Pick **Cloudflare R2** or **Supabase Storage** (S3 API).

- Create a bucket named `docmate` (or your choice — match `S3_BUCKET`).
- Create an S3 API access key + secret.
- Note the S3 endpoint. For R2 it looks like
  `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` with `S3_REGION=auto`.

### 3. Deploy the backend container

**Render (primary):**

1. Push this repo to GitHub.
2. Render Dashboard → **New → Blueprint** → select the repo. Render reads
   [`../render.yaml`](../render.yaml) and creates the `docmate-backend` web
   service (built from `backend/Dockerfile`, health check `/health`) and,
   unless you removed it, a `docmate-db` Postgres.
3. Fill every env var marked `sync: false` in the dashboard (the secrets +
   `CORS_ORIGINS` + LLM fields). If you provisioned Neon/Supabase in step 1,
   remove the `databases:` block / `fromDatabase` mapping first and paste your
   own `DATABASE_URL`.
4. Deploy. The service comes up green once `/health` returns `{"status":"ok"}`.

**Fly.io (alternative):** use [`../deploy/fly.toml`](../deploy/fly.toml) — set
secrets with `fly secrets set ...`, then `fly deploy`.

### 4. Run migrations + seed against the prod DB

Run once, from a machine that can reach the prod database, with
`DATABASE_URL` pointed at production:

```bash
cd backend
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME'
pip install -r requirements.txt          # if not already
alembic upgrade head                      # creates schema + enables pgvector
python -m scripts.seed                    # seeds demo reception + doctor users
```

You can also run these from the host's shell (Render Shell / `fly ssh console`)
inside the deployed container, where `DATABASE_URL` is already set:

```bash
alembic upgrade head && python -m scripts.seed
```

Seeded demo logins: `reception@demo` / `demo1234` and `doctor@demo` / `demo1234`.

### 5. Deploy the frontend to Vercel

1. Vercel → **New Project** → import the repo.
2. **Root Directory:** `frontend`. Framework preset: **Next.js** (auto).
   Build command `npm run build`, install `npm ci` (see
   [`../frontend/vercel.json`](../frontend/vercel.json)).
3. Add env var **`NEXT_PUBLIC_API_URL`** = your backend URL from step 3
   (e.g. `https://docmate-backend.onrender.com`), Environment: Production.
   See [`../frontend/.env.production.example`](../frontend/.env.production.example).
4. Deploy. Note the resulting URL (e.g. `https://doc-mate.vercel.app`).

### 6. Wire production CORS

Back on the backend host, set **`CORS_ORIGINS`** to include the Vercel
domain(s), comma-separated, then redeploy/restart the backend:

```
CORS_ORIGINS=https://doc-mate.vercel.app
```

Include preview domains too if judges will use them, e.g.
`https://doc-mate.vercel.app,https://doc-mate-git-main-yourteam.vercel.app`.
The backend reads `CORS_ORIGINS` from the environment (comma-separated) — no
code change needed.

---

## Smoke-check checklist

After all six steps:

- [ ] `GET https://<backend>/health` returns `{"status":"ok"}`.
- [ ] `GET https://<backend>/docs` loads the FastAPI interactive docs.
- [ ] Frontend loads at the Vercel URL with no console CORS errors.
- [ ] Login as `doctor@demo` / `demo1234` succeeds (JWT issued).
- [ ] Login as `reception@demo` / `demo1234` succeeds.
- [ ] Reception can create a patient and upload a document (lands in the
      S3 bucket; check the storage dashboard).
- [ ] Document ingestion reaches a terminal status (works in stub mode with
      no LLM key).
- [ ] Doctor opens the patient and sees the citation-backed snapshot.
- [ ] No patient content appears in backend logs (ids/statuses only).

---

## Notes & troubleshooting

- **`type "vector" does not exist` on migrate** — the DB doesn't have pgvector
  available, or `alembic upgrade head` didn't run against it. Confirm the
  managed instance supports pgvector and re-run the migration.
- **CORS errors in the browser** — `CORS_ORIGINS` on the backend must exactly
  match the frontend origin (scheme + host, no trailing slash) and the backend
  must have been restarted after the change.
- **`NEXT_PUBLIC_API_URL` changes don't apply** — it is inlined at build time;
  redeploy the frontend after changing it.
- **Wrong DB driver** — `DATABASE_URL` must start with `postgresql+psycopg://`
  (not plain `postgres://`), or SQLAlchemy will fail to connect.
- **Workers/memory** — tune `WEB_CONCURRENCY` down to `1` on very small
  instances if the container is OOM-killed.
