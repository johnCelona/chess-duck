"""Runtime configuration. The only module that reads the environment (ADR-0014)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

import platformdirs
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DG_", env_file=".env", extra="ignore")

    env: Literal["dev", "prod", "test"] = "prod"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=0, le=65535)
    data_dir: Path | None = None
    api_token: SecretStr | None = None
    allowed_origins: Annotated[tuple[str, ...], NoDecode] = ()
    allowed_hosts: Annotated[tuple[str, ...], NoDecode] = ()
    max_engines: int | None = Field(default=None, ge=1, le=64)
    max_hash_mb_total: int = Field(default=1024, ge=16)
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    lichess_enabled: bool = False
    fake_engine: bool = False

    @field_validator("allowed_origins", "allowed_hosts", mode="before")
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @property
    def resolved_data_dir(self) -> Path:
        if self.data_dir is not None:
            return self.data_dir.expanduser().resolve()
        return Path(platformdirs.user_data_dir("DuckGambit", appauthor=False))

    @property
    def origins(self) -> tuple[str, ...]:
        if self.env == "dev":
            return tuple(dict.fromkeys((*self.allowed_origins, *DEV_ORIGINS)))
        return self.allowed_origins

    @property
    def engine_budget(self) -> int:
        if self.max_engines is not None:
            return self.max_engines
        return max(1, min(8, (os.cpu_count() or 2) - 1))
