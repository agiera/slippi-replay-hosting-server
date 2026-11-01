from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.replay import ReplayPlayerPublic


U32 = Annotated[int, Field(ge=0, le=0xFFFFFFFF)]
S32 = Annotated[int, Field(ge=-0x80000000, le=0x7FFFFFFF)]
HexU32 = Annotated[str, Field(pattern=r"^[0-9a-f]{8}$")]


class ControllerProbeDiagnostics(BaseModel):
    """Per-SI-channel state of the PPC controller-metadata probe (diag v2)."""

    model_config = {"extra": "forbid", "strict": True}

    tag: HexU32
    calls: U32
    attempts: U32
    rearms: U32
    runs: U32
    n_chunks: U32
    comcsr: HexU32
    iobuf0: HexU32
    cmd_idx: int = Field(ge=-0x80000000, le=0x7FFFFFFF)
    valid_len: int = Field(ge=0, le=0xFFFF)


class TcpDiagnostics(BaseModel):
    """Stream data socket MSS: IOS drops to 536 after consecutive RTOs; firmware raises it back."""

    model_config = {"extra": "forbid", "strict": True}

    mss_start: U32
    mss_min: U32
    raises: U32
    raise_result: S32
    mss_after_raise: U32


class FirmwareDiagnostics(BaseModel):
    model_config = {"extra": "forbid", "strict": True}

    version: Literal[1, 2]
    bytes_sent: int = Field(ge=0, le=0xFFFFFFFF)
    stalls: int = Field(ge=0, le=0xFFFFFFFF)
    max_stall_ms: int = Field(ge=0, le=0xFFFFFFFF)
    max_backlog: int = Field(ge=0, le=0xFFFFFFFF)
    last_socket_error: int = Field(ge=-0x80000000, le=0)
    start_result: int = Field(ge=-4, le=1)
    cancel_reason: int = Field(ge=0, le=3)
    footer_result: int = Field(ge=-4, le=1)
    finish_result: int = Field(ge=-4, le=1)
    fallback_result: int = Field(ge=-4, le=1)
    local_available: Literal[0, 1]
    game_end_seen: Literal[0, 1]
    tcp: TcpDiagnostics | None = None
    controller_ports: list[ControllerProbeDiagnostics] | None = Field(default=None, max_length=4)


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


class LiveSourceStatusPublic(BaseModel):
    source_name: str
    username: str
    upload_session_id: str | None = None
    stream_game_id: str | None = None
    connected: bool
    repositories: list[str]
    resolved_tournament_name: str | None = None
    stage_preview: int | None = None
    connected_at: datetime | None = None
    updated_at: datetime | None = None
    last_activity_at: datetime | None = None
    stream_phase: str | None = None
    rank_lookup_complete: bool = False
    player_preview: list[ReplayPlayerPublic] = Field(default_factory=list)


class LiveReplayEventPublic(BaseModel):
    source_name: str
    username: str
    upload_session_id: str | None = None
    stream_game_id: str | None = None
    repository: str
    resolved_tournament_name: str | None = None
    filename: str
    status: str
    timestamp: datetime


class StreamStatusResponse(BaseModel):
    tournament: TournamentSeriesPublic | None
    sources: list[LiveSourceStatusPublic]
    events: list[LiveReplayEventPublic]
