from datetime import datetime

from pydantic import BaseModel, Field


class TournamentSeriesPublic(BaseModel):
    id: int
    name: str
    repository_id: int
    repository_name: str | None = None
    is_public: bool = False
    provider: str | None = None
    slug: str | None = None
    current_tournament_name: str | None = None
    current_tournament_name_fetched_at: datetime | None = None

    model_config = {"from_attributes": True}


class TournamentSeriesCreateRequest(BaseModel):
    name: str
    is_public: bool = False
    provider: str | None = None
    slug: str | None = None


class TournamentSeriesUpdateRequest(BaseModel):
    name: str | None = None
    is_public: bool | None = None
    provider: str | None = None
    slug: str | None = None
    refresh_current_tournament_name: bool = False


class TournamentSourcesUpdateRequest(BaseModel):
    source_ids: list[int]


class SourcePublic(BaseModel):
    id: int
    source_name: str
    token_prefix: str
    username: str


class LiveSourcePlayerPreviewPublic(BaseModel):
    port: int | None = None
    display_name: str | None = None
    tag: str | None = None
    slippi_code: str | None = None
    firmware: str | None = None
    rank: str | None = None
    rating: int | None = None


class LiveSourceStatusPublic(BaseModel):
    source_name: str
    username: str
    connected: bool
    repositories: list[str]
    resolved_tournament_name: str | None = None
    updated_at: datetime | None = None
    player_preview: list[LiveSourcePlayerPreviewPublic] = Field(default_factory=list)


class LiveReplayEventPublic(BaseModel):
    source_name: str
    username: str
    repository: str
    resolved_tournament_name: str | None = None
    filename: str
    status: str
    timestamp: datetime


class StreamStatusResponse(BaseModel):
    tournament: TournamentSeriesPublic | None
    sources: list[LiveSourceStatusPublic]
    events: list[LiveReplayEventPublic]
