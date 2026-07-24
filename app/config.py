"""Centralised, env-driven configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Upload limits
    max_upload_mb: int = 20

    # LLM fallback — set to "openai", "anthropic", "gemini", or "none"
    llm_provider: Literal["openai", "anthropic", "gemini", "none"] = "none"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Internal paths
    upload_dir: Path = Path("/tmp/quiz_parser_uploads")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
