from typing import Literal

from pydantic import BaseModel, Field


class Limit(BaseModel):
    type: Literal["nodes", "depth", "time"] = "nodes"
    value: int = Field(default=100_000, ge=1)


class AnalyseRequest(BaseModel):
    fen: str
    limit: Limit = Field(default_factory=Limit)
    multipv: int = Field(default=3, ge=1, le=10)
    overrides: dict[str, object] = Field(default_factory=dict)


class SettingsPayload(BaseModel):
    limit: Limit = Field(default_factory=Limit)
    multipv: int = Field(default=3, ge=1, le=10)
    options: dict[str, object] = Field(default_factory=dict)
