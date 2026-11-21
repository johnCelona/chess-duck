"""Shared pieces of the wire contract (ADR-0002): camelCase JSON, typed ids, problems."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
STREAM_PATTERN = r"^(match|duck|job):[a-z0-9][a-z0-9_-]{0,63}$"

Id = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
StreamName = Annotated[str, StringConstraints(pattern=STREAM_PATTERN)]


class Wire(BaseModel):
    """Base for everything that crosses the API: snake_case in Python, camelCase in JSON."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class WireIn(Wire):
    """Request bodies reject unknown fields, so typos fail loudly."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class FieldError(Wire):
    location: str
    message: str


class Problem(Wire):
    """RFC 9457 problem document with a stable machine-readable `code`."""

    type: str = "about:blank"
    title: str
    status: int
    code: str = Field(
        description="Stable identifier clients can switch on, e.g. engine.not_installed"
    )
    detail: str | None = None
    errors: list[FieldError] = Field(default_factory=list)
