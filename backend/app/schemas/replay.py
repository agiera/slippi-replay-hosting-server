from pydantic import BaseModel


class ReplayPlayerPublic(BaseModel):
    name: str | None
    connect_code: str | None
    character_id: int | None
    character_color: int | None
    costume_id: int | None
    # Team colour (0 red, 1 blue, 2 green); set only when the game is in team mode.
    team_id: int | None = None
    port: int | None
    type: int | None = None
    is_cpu: bool = False
    is_winner: int | None
    rank: str | None
    rating: int | None


class ReplayFilePublic(BaseModel):
    id: int
    folder: str
    name: str
    stream_game_id: str | None = None
    source_name: str | None = None
    resolved_tournament_name: str | None = None
    repository_is_public: bool = False
    download_url: str | None = None
    size_bytes: int
    birth_time: str | None
    player_1: str | None
    player_2: str | None
    player_1_info: ReplayPlayerPublic | None
    player_2_info: ReplayPlayerPublic | None
    players: list[ReplayPlayerPublic] = []
    stage: int | None
    # Melee team mode, read from the replay by peppi. Players' team_id says who is on which team.
    is_teams: bool = False
    game_duration: int | None
    datetime_played: str | None
    handwarmer_label: str | None = None
    handwarmer_reason: str | None = None
    handwarmer_score: float | None = None
    handwarmer_version: int | None = None

    model_config = {"from_attributes": True}


class ReplayFileListResponse(BaseModel):
    items: list[ReplayFilePublic]
    next_cursor: int | None
