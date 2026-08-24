# Development — local quickstart

How to run the full Doc-mate stack on your machine. The goal: start the backing
services with one command, then run the backend and frontend directly.

For the architecture and product context, read [`PROJECT.md`](PROJECT.md) first.

## Prerequisites

- **Docker** (with Docker Compose v2 — `docker compose`, not `docker-compose`)
- **Python 3.11+**
- **Node.js 20+** (with npm)
- A POSIX shell or PowerShell — commands below are cross-platform unless noted.

## The stack, and what runs where

| Layer            | How it runs        | Port   |
|------------------|--------------------|--------|
| Postgres + pgvector | Docker (`infra/`) | `5432` |
| MinIO (S3 API)   | Docker (`infra/`)  | `9000` |
| MinIO console    | Docker (`infra/`)  | `9001` |
| Backend (FastAPI)| directly, `uvicorn`| `8000` |
| Frontend (Next.js)| directly, `npm`   | `3000` |

Only the databases run in Docker. The backend and frontend run on your host for
fast reloads.

## Run it — in this exact order

### 1. Start backing services (Postgres + MinIO)

From the repository root:

```bash
docker compose -f infra/docker-compose.yml up -d
```

This starts Postgres (pgvector enabled on first boot), MinIO, and a one-shot job
that creates the `docmate` bucket. Give it a few seconds; check health with:

```bash
docker compose -f infra/docker-compose.yml ps
```

Details, credentials, and troubleshooting for these services live in
[`../infra/README.md`](../infra/README.md).

### 2. Backend (FastAPI, port 8000)

```bash
cd backend

# create + activate a virtualenv
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1

# install dependencies
pip install -r requirements.txt

# configure env — copy the backend example and adjust if needed
cp .env.example .env             # Windows (PowerShell): Copy-Item .env.example .env

# apply database migrations, then seed demo data
alembic upgrade head
python -m scripts.seed           # seeds demo users + sample patient (see note below)

# run the API with autoreload
uvicorn app.main:app --reload --port 8000
```

API is now at <http://localhost:8000> (interactive docs at `/docs`).

> The backend has its own `backend/.env.example` — that's the file the backend
> actually loads. The repo-root `.env.example` is a shared reference for every
> variable across the whole project; keep names in sync with it and PROJECT.md §11.

### 3. Frontend (Next.js, port 3000)

In a second terminal:

```bash
cd frontend

npm install

# configure env — Next.js reads .env.local
cp .env.example .env.local       # Windows (PowerShell): Copy-Item .env.example .env.local

npm run dev
```

App is now at <http://localhost:3000>.

> The frontend has its own `frontend/.env.example`. It needs
> `NEXT_PUBLIC_API_URL=http://localhost:8000` to reach the backend.

## Handy URLs & credentials (local dev only)

| What            | URL                          | Credentials                     |
|-----------------|------------------------------|---------------------------------|
| Frontend        | <http://localhost:3000>      | demo logins below               |
| Backend API docs| <http://localhost:8000/docs> | —                               |
| MinIO console   | <http://localhost:9001>      | `minioadmin` / `minioadmin`     |
| Postgres        | `localhost:5432`             | `docmate` / `docmate` (db `docmate`) |

### Demo logins (seeded)

| Role      | Username         | Password   |
|-----------|------------------|------------|
| Reception | `reception@demo` | `demo1234` |
| Doctor    | `doctor@demo`    | `demo1234` |

## Stopping

```bash
# stop the backend / frontend: Ctrl-C in each terminal

# stop the Docker services (data preserved)
docker compose -f infra/docker-compose.yml down

# stop AND wipe all local data (fresh DB + empty storage next time)
docker compose -f infra/docker-compose.yml down -v
```

## Troubleshooting

- **Port already in use (5432 / 9000 / 3000 / 8000).** Something else is bound to
  the port. Stop the other process, or change the host-side port mapping in
  `infra/docker-compose.yml` (and the matching URL in your `.env`).
- **Backend can't connect to the database.** Make sure step 1 is up and healthy
  (`docker compose -f infra/docker-compose.yml ps`). Confirm `DATABASE_URL` points
  at `localhost:5432` with user/password/db all `docmate`.
- **`type "vector" does not exist` on migrate.** The pgvector init script only runs
  on a fresh data directory. If Postgres initialized before the script was present,
  reset with `docker compose -f infra/docker-compose.yml down -v` and start again.
- **File upload / storage errors.** Confirm the `docmate` bucket exists — the
  `createbuckets` job should show `Exited (0)`. Re-run it with
  `docker compose -f infra/docker-compose.yml up createbuckets`. Check `S3_ENDPOINT`
  is the API port `9000`, not the console port `9001`.
- **Frontend calls fail / CORS.** Confirm `NEXT_PUBLIC_API_URL` is
  `http://localhost:8000` and the backend's `CORS_ORIGINS` includes
  `http://localhost:3000`.
- **Docker Desktop not running.** All `docker compose` commands fail immediately —
  start Docker Desktop first.

> Exact backend commands (`alembic`, seed module name) may evolve as the backend
> lands — check `backend/README.md` if one drifts from what's shown here.
