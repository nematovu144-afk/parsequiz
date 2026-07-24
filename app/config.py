"""Centralised, env-driven configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Upload limits
    max_upload_mb: int = 20

    # LLM fallback — set to "openai", "anthropic", "gemini", or "none"
    llm_provider: Literal["openai", "anthropic", "gemini", "none"] = "none"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    # Left blank by default — each provider call picks its own sensible
    # default model (see app/llm/fallback.py) so switching LLM_PROVIDER
    # without also setting LLM_MODEL can't silently send the wrong
    # provider's model name (e.g. an OpenAI model id to Anthropic's API).
    llm_model: str = ""

    # Internal paths
    upload_dir: Path = Path("/tmp/quiz_parser_uploads")

    # Job store. Local dev default matches docker-compose.yml's Postgres
    # service; override via .env / DATABASE_URL for a hosted instance.
    # SQLAlchemy model/query code is dialect-agnostic.
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/quiz_parser"

    @field_validator("database_url")
    @classmethod
    def _use_async_postgres_driver(cls, v: str) -> str:
        """Managed-hosting providers (Render, Heroku, ...) hand out a plain
        postgres:// / postgresql:// URL, which SQLAlchemy's async engine
        can't use directly — it needs an async driver named in the scheme."""
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
