from __future__ import annotations

from typing import Literal

from pydantic import Field

from duckgambit.api.schemas.base import Wire, WireIn
from duckgambit.domain.arena import STARTING_FEN
from duckgambit.services.engines import Analysis, DescribedOption, EngineListing
from duckgambit.services.records import EngineProfile


class EngineOut(Wire):
    id: str
    name: str
    version: str
    license: str
    homepage: str
    source_url: str
    status: Literal["installed", "not_installed", "installing", "unavailable"]
    fingerprint: str | None = Field(description="Start of the installed binary's sha256")

    @classmethod
    def of(cls, listing: EngineListing) -> EngineOut:
        return cls.model_validate(listing)


class EngineOptionOut(Wire):
    name: str
    type: str
    default: str | int | bool | None
    min: int | None
    max: int | None
    choices: list[str]
    user_settable: bool

    @classmethod
    def of(cls, described: DescribedOption) -> EngineOptionOut:
        option = described.option
        return cls(
            name=option.name,
            type=option.type,
            default=option.default,
            min=option.min,
            max=option.max,
            choices=list(option.choices),
            user_settable=described.user_settable,
        )


class AnalysisRequest(WireIn):
    """A diagnostic search. Node-limited only: wall-clock limits are not reproducible."""

    fen: str = Field(default=STARTING_FEN, max_length=100)
    nodes: int = Field(default=100_000, ge=1, le=5_000_000)
    multi_pv: int = Field(default=3, ge=1, le=10, alias="multiPV")
    hash_mb: int = Field(default=16, ge=1, le=1024)


class AnalysisLineOut(Wire):
    move: str
    san: str
    cp: int | None
    mate: int | None
    wdl: tuple[int, int, int] | None
    pv: list[str]


class AnalysisOut(Wire):
    engine_name: str
    depth: int
    nodes: int
    lines: list[AnalysisLineOut]

    @classmethod
    def of(cls, analysis: Analysis) -> AnalysisOut:
        return cls.model_validate(analysis)


class EngineProfileBody(WireIn):
    name: str = Field(min_length=1, max_length=40)
    nodes: int = Field(ge=1, le=5_000_000)
    multi_pv: int = Field(ge=1, le=10, alias="multiPV")
    hash_mb: int = Field(ge=1, le=1024)

    def to_record(self, engine_id: str) -> EngineProfile:
        return EngineProfile(engine_id, self.name.strip(), self.nodes, self.multi_pv, self.hash_mb)


class EngineProfileOut(Wire):
    name: str
    nodes: int
    multi_pv: int = Field(alias="multiPV")
    hash_mb: int

    @classmethod
    def of(cls, profile: EngineProfile) -> EngineProfileOut:
        return cls(
            name=profile.name,
            nodes=profile.nodes,
            multi_pv=profile.multipv,
            hash_mb=profile.hash_mb,
        )
