# infra — local development services

One command brings up everything the Doc-mate backend needs to run locally:
**PostgreSQL (with pgvector)** for relational data + embeddings, and **MinIO**
(S3-compatible object storage) for raw uploaded files.

These are development defaults only — do not reuse these credentials anywhere real.

## Services

| Service         | Image                    | What it is                                             | Ports        |
|-----------------|--------------------------|--------------------------------------------------------|--------------|
| `postgres`      | `pgvector/pgvector:pg16` | Postgres 16 + `pgvector` (relational data + vectors)   | `5432`       |
| `minio`         | `minio/minio`            | S3-compatible object storage for raw uploads           | `9000`, `9001` |
| `createbuckets` | `minio/mc`               | One-shot job: creates the `docmate` bucket, then exits | —            |

- **Postgres port** `5432` — S3 API is not here; this is the database.
- **MinIO S3 API** `9000` — what the backend talks to (`S3_ENDPOINT`).
- **MinIO console** `9001` — web UI at <http://localhost:9001>.

## Credentials (local dev only)

| Service       | User         | Password     | Database / Bucket |
|---------------|--------------|--------------|-------------------|
| Postgres      | `docmate`    | `docmate`    | `docmate`         |
| MinIO         | `minioadmin` | `minioadmin` | bucket `docmate`  |

Connection string used by the backend:

```
DATABASE_URL=postgresql+psycopg://docmate:docmate@localhost:5432/docmate
```

## Start / stop

Run from the **repository root** (paths in the compose file are relative to `infra/`,
but `-f` lets you invoke it from anywhere):

```bash
# start in the background
docker compose -f infra/docker-compose.yml up -d

# view status / logs
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml logs -f

# stop (data is preserved in named volumes)
docker compose -f infra/docker-compose.yml down

# stop AND delete all data (fresh start — re-runs the pgvector init script)
docker compose -f infra/docker-compose.yml down -v
```

## How initialization works

- **pgvector**: `postgres/init/01-extensions.sql` is mounted into
  `/docker-entrypoint-initdb.d`. Postgres runs it **once**, on the first boot of an
  empty data directory, so the `vector` extension is ready before the app connects.
  If you change that script, run `down -v` to re-trigger it.
- **Bucket**: the `createbuckets` job waits for MinIO, then runs
  `mc mb --ignore-existing local/docmate`. It is idempotent — it succeeds whether or
  not the bucket already exists, then exits. Seeing it in an `Exited (0)` state is
  the expected, healthy outcome.

## Verify it's working

```bash
# Postgres reachable and pgvector present
docker exec -it docmate-postgres psql -U docmate -d docmate -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"

# MinIO bucket exists (open the console and sign in with minioadmin / minioadmin)
open http://localhost:9001
```

## Notes

- The compose file only provisions **backing services**. The FastAPI backend and
  Next.js frontend are run directly on your machine during development — see
  [`../docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) for the full stack quickstart.
- Data lives in named Docker volumes (`docmate_postgres-data`, `docmate_minio-data`),
  not in the repo, so it survives `down` but is removed by `down -v`.
