-- Runs once on first initialization of an empty Postgres data directory
-- (via /docker-entrypoint-initdb.d). Enables the pgvector extension so the
-- app can store and query embeddings alongside relational data.
CREATE EXTENSION IF NOT EXISTS vector;
