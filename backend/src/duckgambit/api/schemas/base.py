"""Shared pieces of the wire contract (ADR-0002): camelCase JSON, typed ids, problems."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints
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


class Wdl(Wire):
    """Win, draw and loss chances per mille, from the mover's point of view."""

    win: int
    draw: int
    loss: int


def _wdl_from_triple(value: Any) -> Any:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return {"win": value[0], "draw": value[1], "loss": value[2]}
    return value


# An object rather than a 3-item array: fixed-length arrays generate poorly in C# and TS.
WdlField = Annotated[Wdl | None, BeforeValidator(_wdl_from_triple)]


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
