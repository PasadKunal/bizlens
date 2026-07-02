"""Central configuration, loaded from environment variables / .env.

All tunables live here so that the analytics, api, dashboard, and reporting
layers read from a single source of truth. See ``.env.example`` for the full
list of supported variables.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for BizLens."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Postgres -----------------------------------------------------------
    # The application role. Analytics queries should use ANALYST_DATABASE_URL
    # (a SELECT-only role) — never the admin role.
    database_url: str = Field(
        default="postgresql+psycopg://bizlens:bizlens@localhost:5432/bizlens",
        alias="DATABASE_URL",
    )
    analyst_database_url: str = Field(
        default="postgresql+psycopg://bizlens_readonly:readonly@localhost:5432/bizlens",
        alias="ANALYST_DATABASE_URL",
    )

    # --- Redis --------------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    kpi_cache_ttl_seconds: int = Field(default=300, alias="KPI_CACHE_TTL_SECONDS")

    # --- Query sandbox limits ----------------------------------------------
    adhoc_query_timeout_seconds: int = Field(default=10, alias="ADHOC_QUERY_TIMEOUT")
    adhoc_query_row_cap: int = Field(default=10_000, alias="ADHOC_QUERY_ROW_CAP")

    # --- Auth ---------------------------------------------------------------
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiry_minutes: int = Field(default=60, alias="JWT_EXPIRY_MINUTES")

    # Built-in analyst accounts for local/dev use. In production this is replaced
    # by a real user store; both map to the read-only PG role but carry a
    # different row-level-security scope (data-scoping demo).
    #   analyst     -> scope ALL (sees every country)
    #   analyst_br  -> scope BR  (sees only Brazil rows)
    dev_username: str = Field(default="analyst", alias="DEV_USERNAME")
    dev_password: str = Field(default="analyst", alias="DEV_PASSWORD")
    dev_scoped_username: str = Field(default="analyst_br", alias="DEV_SCOPED_USERNAME")
    dev_scoped_scope: str = Field(default="BR", alias="DEV_SCOPED_SCOPE")
    analyst_role: str = Field(default="bizlens_readonly", alias="ANALYST_ROLE")

    # --- OpenAI -------------------------------------------------------------
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")

    # NL-to-SQL embedding backend: "local" (hashing, offline) or "openai".
    embed_backend: str = Field(default="local", alias="EMBED_BACKEND")

    # --- Anomaly detection --------------------------------------------------
    anomaly_sigma_threshold: float = Field(default=2.5, alias="ANOMALY_SIGMA")

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
