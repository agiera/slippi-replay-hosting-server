from pydantic import BaseModel


class ReplayPlayerPublic(BaseModel):
    name: str | None
    connect_code: str | None
    character_id: int | None
    character_color: int | None
    port: int | None
    is_winner: int | None
    rank: str | None
    rating: int | None


class ReplayFilePublic(BaseModel):
    id: int
    folder: str
    name: str
    source_name: str | None = None
    resolved_tournament_name: str | None = None
    size_bytes: int
    birth_time: str | None
    player_1: str | None
    player_2: str | None
    player_1_info: ReplayPlayerPublic | None
    player_2_info: ReplayPlayerPublic | None
    stage: int | None
    game_duration: int | None
    datetime_played: str | None

    model_config = {"from_attributes": True}


class ReplayFileListResponse(BaseModel):
    items: list[ReplayFilePublic]
    next_cursor: int | None
