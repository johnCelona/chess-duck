from __future__ import annotations

from typing import Any

from pydantic import Field

from duckgambit.api.schemas.base import Wire, WireIn
from duckgambit.domain.balance import Balance
from duckgambit.domain.duck import Avatar, Duck
from duckgambit.services.ducks import HeadlineRating


class StatsModel(WireIn):
    calculation: int = Field(ge=0, le=100)
    memory: int = Field(ge=0, le=100)
    aggression: int = Field(ge=0, le=100)
    solidity: int = Field(ge=0, le=100)
    creativity: int = Field(ge=0, le=100)
    speed: int = Field(ge=0, le=100)


class AvatarModel(WireIn):
    species: str = Field(default="mallard", max_length=32)
    skin: str = Field(default="default", max_length=32)
    accessories: list[str] = Field(default_factory=list, max_length=8)

    def to_domain(self) -> Avatar:
        return Avatar(self.species, self.skin, tuple(self.accessories))


class HatchRequest(WireIn):
    name: str = Field(min_length=1, max_length=60)
    avatar: AvatarModel | None = None
    stats: StatsModel | None = Field(
        default=None, description="Omit for the default spread. Must fit the level-1 stat budget."
    )


class GrowthOut(Wire):
    stage: str
    level: int
    xp: int
    stat_budget: int
    stat_cap: int


class CareOut(Wire):
    hunger: float
    energy: float
    mood: float
    last_fed_at: str | None


class KnowledgeSummaryOut(Wire):
    repertoire_size: int
    puzzle_memory_size: int
    principles: list[str]
    motifs: dict[str, int]


class HeadlineRatingOut(Wire):
    """The rating shown beside a duck. Provisional until enough rated games are played."""

    value: float
    deviation: float
    games: int
    provisional: bool
    context_id: str | None = Field(
        description="Rating context this number belongs to; null for the pre-game placeholder"
    )


class DuckOut(Wire):
    id: str
    name: str
    avatar: AvatarModel
    growth: GrowthOut
    stats: StatsModel
    care: CareOut
    knowledge: KnowledgeSummaryOut
    rating: HeadlineRatingOut
    created_at: str
    origin: str | None
    stream: str = Field(description="Event stream for this duck")

    @classmethod
    def of(cls, duck: Duck, rating: HeadlineRating, balance: Balance) -> DuckOut:
        return cls(
            id=duck.id,
            name=duck.name,
            avatar=AvatarModel(
                species=duck.avatar.species,
                skin=duck.avatar.skin,
                accessories=list(duck.avatar.accessories),
            ),
            growth=GrowthOut(
                stage=duck.growth.stage,
                level=duck.growth.level,
                xp=duck.growth.xp,
                stat_budget=balance.stat_budget(duck.growth.level),
                stat_cap=balance.stage_for(duck.growth.level).stat_cap,
            ),
            stats=StatsModel(**duck.stats),
            care=CareOut.model_validate(duck.care),
            knowledge=KnowledgeSummaryOut(
                repertoire_size=len(duck.knowledge.repertoire),
                puzzle_memory_size=len(duck.knowledge.puzzle_memory),
                principles=list(duck.knowledge.principles),
                motifs=dict(duck.knowledge.motifs),
            ),
            rating=HeadlineRatingOut(
                value=round(rating.value, 1),
                deviation=round(rating.deviation, 1),
                games=rating.games,
                provisional=rating.provisional,
                context_id=rating.context_id,
            ),
            created_at=duck.created_at,
            origin=duck.origin,
            stream=f"duck:{duck.id}",
        )


class DuckFile(Wire):
    """A portable duck export (ADR-0004). The `duck` body is validated by the domain on import."""

    format: str
    schema_version: int
    exported_at: str | None = None
    exported_by: dict[str, Any] | None = None
    duck: dict[str, Any]
