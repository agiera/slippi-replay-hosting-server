from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.file import File
from app.models.game import Game
from app.models.player import Player
from app.schemas.replay import ReplayFileListResponse, ReplayFilePublic, ReplayPlayerPublic
from app.services.slippi_profile import fetch_profile_by_connect_code

router = APIRouter()

_STAGE_NAMES: dict[int, str] = {
    2: "Fountain of Dreams",
    3: "Pokemon Stadium",
    4: "Peach's Castle",
    5: "Kongo Jungle",
    6: "Brinstar",
    7: "Corneria",
    8: "Yoshi's Story",
    9: "Onett",
    10: "Mute City",
    11: "Rainbow Cruise",
    12: "Jungle Japes",
    13: "Great Bay",
    14: "Hyrule Temple",
    15: "Brinstar Depths",
    16: "Yoshi's Island",
    17: "Green Greens",
    18: "Fourside",
    19: "Mushroom Kingdom I",
    20: "Mushroom Kingdom II",
    22: "Venom",
    23: "Poke Floats",
    24: "Big Blue",
    25: "Icicle Mountain",
    27: "Flat Zone",
    28: "Dream Land N64",
    29: "Yoshi's Island N64",
    30: "Kongo Jungle N64",
    31: "Battlefield",
    32: "Final Destination",
}

_CHARACTER_NAMES: dict[int, str] = {
    0: "Captain Falcon",
    1: "Donkey Kong",
    2: "Fox",
    3: "Mr. Game & Watch",
    4: "Kirby",
    5: "Bowser",
    6: "Link",
    7: "Luigi",
    8: "Mario",
    9: "Marth",
    10: "Mewtwo",
    11: "Ness",
    12: "Peach",
    13: "Pikachu",
    14: "Ice Climbers",
    15: "Jigglypuff",
    16: "Samus",
    17: "Yoshi",
    18: "Zelda",
    19: "Sheik",
    20: "Falco",
    21: "Young Link",
    22: "Dr. Mario",
    23: "Roy",
    24: "Pichu",
    25: "Ganondorf",
}


def _parse_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    items = [part.strip() for part in value.split(",") if part.strip()]
    # Preserve first occurrence order while removing duplicates.
    return list(dict.fromkeys(items))


def _extract_repo_collection(folder: str | None) -> tuple[str | None, str | None]:
    if not folder:
        return None, None

    parts = [part for part in folder.split("/") if part]
    if not parts:
        return None, None

    if parts[0] == "uploads":
        repository = parts[1] if len(parts) > 1 else None
        collection = None
        if len(parts) > 2:
            # Legacy uploads used uploads/<repo>/<YYYY>/<MM>/<DD>; avoid treating years as collections.
            maybe_collection = parts[2]
            if not (maybe_collection.isdigit() and len(maybe_collection) == 4):
                collection = maybe_collection
        return repository, collection

    repository = parts[0]
    collection = parts[1] if len(parts) > 1 else None
    return repository, collection


def _matches_rank_filter(rank_values: list[str], player_one_rank: str | None, player_two_rank: str | None) -> bool:
    if not rank_values:
        return True

    if len(rank_values) == 1:
        target = rank_values[0]
        return player_one_rank == target or player_two_rank == target

    first, second = rank_values[0], rank_values[1]
    return (player_one_rank == first and player_two_rank == second) or (
        player_one_rank == second and player_two_rank == first
    )


def _matches_rating_filter(
    min_rating: int | None,
    max_rating: int | None,
    player_one_rating: int | None,
    player_two_rating: int | None,
) -> bool:
    if min_rating is None and max_rating is None:
        return True

    if player_one_rating is None or player_two_rating is None:
        return False

    if min_rating is not None and (player_one_rating < min_rating or player_two_rating < min_rating):
        return False

    if max_rating is not None and (player_one_rating > max_rating or player_two_rating > max_rating):
        return False

    return True


@router.get("/filters")
def list_replay_filters(db: Session = Depends(get_db)) -> dict[str, list[str]]:
    folders = db.scalars(select(File.folder).distinct()).all()
    collection_names = db.scalars(select(ApiToken.collection_name).distinct()).all()

    repositories: set[str] = set()
    collections = {name for name in collection_names if name}

    for folder in folders:
        repository, collection = _extract_repo_collection(folder)
        if repository:
            repositories.add(repository)
        # Keep parsed collection as fallback for non-token historical imports.
        if collection:
            collections.add(collection)

    return {
        "repositories": sorted(repositories),
        "collections": sorted(collections),
    }


@router.get("/files", response_model=ReplayFileListResponse)
def list_files(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    cursor: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    keyword: str | None = Query(None),
    character: str | None = Query(None),
    ranked: int | None = Query(None, ge=0, le=1),
    player: str | None = Query(None),
    rank: str | None = Query(None),
    min_rank: int | None = Query(None),
    max_rank: int | None = Query(None),
    repository: str | None = Query(None),
    collection: str | None = Query(None),
) -> ReplayFileListResponse:
    player_one = aliased(Player)
    player_two = aliased(Player)

    stmt_ids = (
        select(File._id)
        .select_from(File)
        .join(Game, Game.file_id == File._id, isouter=True)
        .join(Player, Player.game_id == Game._id, isouter=True)
    )

    conditions = []

    if cursor is not None:
        conditions.append(File._id < cursor)

    if date_from:
        conditions.append(Game.start_time >= date_from)

    if date_to:
        conditions.append(Game.start_time <= f"{date_to}T23:59:59.999Z")

    if keyword:
        for kw in [part.lower() for part in keyword.split() if part.strip()]:
            pattern = f"%{kw}%"
            matching_stage_ids = [sid for sid, name in _STAGE_NAMES.items() if kw in name.lower()]
            matching_char_ids = [cid for cid, name in _CHARACTER_NAMES.items() if kw in name.lower()]
            player_for_keyword = aliased(Player)
            player_kw_match = exists(
                select(player_for_keyword._id)
                .select_from(player_for_keyword)
                .where(
                    and_(
                        player_for_keyword.game_id == Game._id,
                        or_(
                            player_for_keyword.display_name.ilike(pattern),
                            player_for_keyword.connect_code.ilike(pattern),
                            player_for_keyword.tag.ilike(pattern),
                            player_for_keyword.character_id.in_(matching_char_ids) if matching_char_ids else False,
                        ),
                    )
                )
            )
            kw_clauses: list = [
                File.folder.ilike(pattern),
                File.name.ilike(pattern),
                player_kw_match,
            ]
            if matching_stage_ids:
                kw_clauses.append(Game.stage.in_(matching_stage_ids))
            conditions.append(or_(*kw_clauses))

    if character:
        character_ids = set()
        for raw in character.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                character_ids.add(int(raw))
            except ValueError:
                continue
        if character_ids:
            for character_id in character_ids:
                player_for_character = aliased(Player)
                conditions.append(
                    exists(
                        select(player_for_character._id)
                        .select_from(player_for_character)
                        .where(
                            and_(
                                player_for_character.game_id == Game._id,
                                player_for_character.character_id == character_id,
                            )
                        )
                    )
                )

    if ranked is not None:
        conditions.append(Game.is_ranked == ranked)

    if player:
        player_pattern = f"%{player.strip()}%"
        conditions.append(
            or_(
                Player.connect_code.ilike(player_pattern),
                Player.display_name.ilike(player_pattern),
                Player.tag.ilike(player_pattern),
                Player.user_id.ilike(player_pattern),
            )
        )

    repository_values = _parse_csv_values(repository)
    if repository_values:
        repo_clauses = []
        for repo_name in repository_values:
            repo_clauses.extend(
                [
                    File.folder == repo_name,
                    File.folder.ilike(f"{repo_name}/%"),
                    File.folder.ilike(f"uploads/{repo_name}/%"),
                ]
            )
        conditions.append(or_(*repo_clauses))

    collection_values = _parse_csv_values(collection)
    if collection_values:
        collection_clauses = []
        for collection_name in collection_values:
            collection_clauses.extend(
                [
                    File.folder == collection_name,
                    File.folder.ilike(f"{collection_name}/%"),
                    File.folder.ilike(f"%/{collection_name}"),
                    File.folder.ilike(f"%/{collection_name}/%"),
                ]
            )
        conditions.append(or_(*collection_clauses))

    rank_values = _parse_csv_values(rank)[:2]

    if conditions:
        stmt_ids = stmt_ids.where(and_(*conditions))

    file_ids = db.scalars(stmt_ids.distinct().order_by(File._id.desc()).limit(limit + 1)).all()
    has_more = len(file_ids) > limit
    file_ids = file_ids[:limit]

    if not file_ids:
        return ReplayFileListResponse(items=[], next_cursor=None)

    details = db.execute(
        select(
            File._id.label("file_id"),
            File.folder.label("folder"),
            File.name.label("name"),
            File.size_bytes.label("size_bytes"),
            File.birth_time.label("birth_time"),
            func.coalesce(player_one.display_name, player_one.tag, player_one.connect_code).label("player_1"),
            func.coalesce(player_two.display_name, player_two.tag, player_two.connect_code).label("player_2"),
            player_one.character_id.label("player_1_character_id"),
            player_one.character_color.label("player_1_character_color"),
            player_one.port.label("player_1_port"),
            player_one.connect_code.label("player_1_connect_code"),
            player_one.is_winner.label("player_1_is_winner"),
            player_two.character_id.label("player_2_character_id"),
            player_two.character_color.label("player_2_character_color"),
            player_two.port.label("player_2_port"),
            player_two.connect_code.label("player_2_connect_code"),
            player_two.is_winner.label("player_2_is_winner"),
            Game.stage.label("stage"),
            Game.last_frame.label("last_frame"),
            Game.start_time.label("datetime_played"),
        )
        .select_from(File)
        .join(Game, Game.file_id == File._id, isouter=True)
        .join(player_one, and_(player_one.game_id == Game._id, player_one.port == 1), isouter=True)
        .join(player_two, and_(player_two.game_id == Game._id, player_two.port == 2), isouter=True)
        .where(File._id.in_(file_ids))
        .order_by(File._id.desc())
    ).all()

    details_by_id = {row.file_id: row for row in details}

    connect_codes = set()
    for row in details:
        if row.player_1_connect_code:
            connect_codes.add(row.player_1_connect_code)
        if row.player_2_connect_code:
            connect_codes.add(row.player_2_connect_code)

    profile_by_code = {code: fetch_profile_by_connect_code(code) for code in connect_codes}

    items = []
    for file_id in file_ids:
        row = details_by_id.get(file_id)
        if row is None:
            items.append(
                ReplayFilePublic(
                    _id=file_id,
                    folder="",
                    name="",
                    size_bytes=0,
                    birth_time=None,
                    player_1=None,
                    player_2=None,
                    player_1_info=None,
                    player_2_info=None,
                    stage=None,
                    game_duration=None,
                    datetime_played=None,
                )
            )
            continue

        duration_seconds = row.last_frame // 60 if row.last_frame is not None else None
        player_one_profile = profile_by_code.get(row.player_1_connect_code)
        player_two_profile = profile_by_code.get(row.player_2_connect_code)
        player_one_rank = player_one_profile.rank if player_one_profile else None
        player_two_rank = player_two_profile.rank if player_two_profile else None
        player_one_rating = player_one_profile.rating if player_one_profile else None
        player_two_rating = player_two_profile.rating if player_two_profile else None

        if not _matches_rank_filter(rank_values, player_one_rank, player_two_rank):
            continue
        if not _matches_rating_filter(min_rank, max_rank, player_one_rating, player_two_rating):
            continue

        items.append(
            ReplayFilePublic(
                _id=row.file_id,
                folder=row.folder,
                name=row.name,
                size_bytes=row.size_bytes,
                birth_time=row.birth_time,
                player_1=row.player_1,
                player_2=row.player_2,
                player_1_info=ReplayPlayerPublic(
                    name=row.player_1,
                    connect_code=row.player_1_connect_code,
                    character_id=row.player_1_character_id,
                    character_color=row.player_1_character_color,
                    port=row.player_1_port,
                    is_winner=row.player_1_is_winner,
                    rank=player_one_rank,
                    rating=player_one_rating,
                ),
                player_2_info=ReplayPlayerPublic(
                    name=row.player_2,
                    connect_code=row.player_2_connect_code,
                    character_id=row.player_2_character_id,
                    character_color=row.player_2_character_color,
                    port=row.player_2_port,
                    is_winner=row.player_2_is_winner,
                    rank=player_two_rank,
                    rating=player_two_rating,
                ),
                stage=row.stage,
                game_duration=duration_seconds,
                datetime_played=row.datetime_played,
            )
        )

    next_cursor = file_ids[-1] if has_more else None

    return ReplayFileListResponse(
        items=items,
        next_cursor=next_cursor,
    )
