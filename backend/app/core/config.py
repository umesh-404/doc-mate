"""Application configuration.

All configuration is env-driven (see .env.example). Sensible defaults are
provided for local development so the app can boot without a populated .env.
Never hardcode secrets or per-environment URLs anywhere else in the codebase.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App -------------------------------------------------------------------
    app_name: str = "Doc-mate"
    environment: str = "local"
    # Comma-separated in env; parsed into a list by the property below.
    cors_origins: str = "http://localhost:3000"

    # Database --------------------------------------------------------------
    database_url: str = "postgresql+psycopg://docmate:docmate@localhost:5432/docmate"

    # Auth ------------------------------------------------------------------
    jwt_secret: str = "dev-insecure-change-me-please-set-a-real-32b-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiry: int = 1440  # minutes

    # Object storage (S3-compatible) ----------------------------------------
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "docmate"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"

    # LLM layer (placeholders; consumed only by app/llm) --------------------
    llm_provider: str | None = None
    llm_model_multimodal: str | None = None
    llm_model_reasoning: str | None = None
    embedding_model: str | None = None
    embedding_dim: int = 1536

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS origins as a clean list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
