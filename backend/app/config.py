# backend/app/config.py
"""Application configuration settings."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = Field(default="development", description="Environment mode")
    DEBUG: bool = Field(default=False)

    # Database
    DATA_DIR: str = Field(default=str(BASE_DIR / "data"))
    DATABASE_URL: str = Field(default="")

    # LLM Settings
    LLM_PROVIDER: str = Field(default="openrouter", description="LLM provider: openrouter, mock, etc.")
    OPENROUTER_API_KEY: str = Field(default="")
    OPENROUTER_MODEL: str = Field(default="openrouter/free")
    OPENROUTER_FALLBACK_MODELS: str = Field(default="")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1")

    # Security & Limits
    FRONTEND_ORIGIN: str = Field(default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")
    MAX_REPO_SIZE_MB: int = Field(default=300)
    CLONE_TIMEOUT_SECONDS: int = Field(default=180)
    MAX_PYTHON_FILES: int = Field(default=2000)
    MAX_ANALYSIS_FILES: int = Field(default=5000)
    MAX_ANALYSIS_TIME_SECONDS: int = Field(default=600)
    MAX_HISTORY_COMMITS: int = Field(default=2000)
    MIN_FREE_DISK_MB: int = Field(default=100)
    MAX_CONCURRENT_JOBS: int = Field(default=2)
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    CACHE_TTL_HOURS: int = Field(default=24)

    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR.parent / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_cors_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGIN.split(",") if o.strip()]

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        os.makedirs(self.DATA_DIR, exist_ok=True)
        db_path = Path(self.DATA_DIR) / "profiler.db"
        # On Windows, sqlite:///C:/... requires 3 slashes
        return f"sqlite:///{db_path.as_posix()}"


settings = Settings()
