# syntax=docker/dockerfile:1
# =============================================================================
# Doc-mate backend — production image (FastAPI + Uvicorn workers)
# =============================================================================
# Multi-stage build:
#   1. builder — compiles/collects dependency wheels into an isolated venv.
#   2. runtime — slim image with only the venv + app code, running as non-root.
#
# Config is 100% env-driven (see backend/.env.example). NO secrets are baked
# into the image — DATABASE_URL, JWT_SECRET, S3_*, LLM_* etc. are injected at
# runtime by the host platform. Stub LLM mode needs no provider key.
# -----------------------------------------------------------------------------

# ----------------------------- Stage 1: builder ------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# build-essential is only needed while building wheels; it never reaches runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Isolated virtualenv we can copy wholesale into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# ----------------------------- Stage 2: runtime ------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Number of Uvicorn worker processes. Override per host/plan (start ~2).
    WEB_CONCURRENCY=2 \
    PORT=8000

# Copy the pre-built virtualenv from the builder (no compilers in final image).
COPY --from=builder /opt/venv /opt/venv

# Create an unprivileged user to run the app.
RUN addgroup --system app && adduser --system --ingroup app --home /app app

WORKDIR /app
COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 8000

# Container-level health probe hitting the app's /health endpoint. Uses the
# stdlib (no curl in slim) so it works without extra packages. Honors $PORT.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
url='http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'); \
sys.exit(0 if urllib.request.urlopen(url, timeout=4).status == 200 else 1)" || exit 1

# Multiple Uvicorn workers for concurrency. $WEB_CONCURRENCY / $PORT are
# read from the environment so the host platform can tune them. Using the
# shell form so the variables expand at container start.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips='*'"]
