"""Doc-mate FastAPI application entrypoint.

Wires CORS, the app lifespan, and all routers. No database connection is
opened at import time or startup — connections are created lazily on first
request so the API boots even when Postgres is unreachable.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    consult,
    documents,
    evaluation,
    governance,
    interop,
    language,
    patients,
    safety,
    summaries,
    surveillance,
    triage,
    users,
    voice,
)
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docmate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: keep it side-effect free (no DB calls) so boot never blocks.
    logger.info("Starting %s (%s)", settings.app_name, settings.environment)
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-assisted patient-context engine for high-volume hospitals.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(documents.router)
app.include_router(summaries.router)
app.include_router(users.router)
# Enhancement routers (Contract v2): clinical safety, interoperability,
# multilingual summaries, and voice intake.
app.include_router(safety.router)
app.include_router(interop.router)
app.include_router(language.router)
app.include_router(voice.router)
# Contract v3: governance (consent + audit), quality evaluation, OPD triage,
# ambient consultation notes, and anonymized public-health surveillance.
app.include_router(governance.router)
app.include_router(evaluation.router)
app.include_router(triage.router)
app.include_router(consult.router)
app.include_router(surveillance.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "running"}


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
