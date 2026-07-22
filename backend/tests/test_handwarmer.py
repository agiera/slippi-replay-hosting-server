from app.services.handwarmer import classify_handwarmer
from app.services.peppi_ingest import ParsedReplayData


def _parsed(*, last_frame: int | None, end_method: str | None, winners: list[int | None]) -> ParsedReplayData:
    players = []
    for index, winner_flag in enumerate(winners, start=1):
        players.append(
            {
                "port": index,
                "type": 0,
                "character_id": 2,
                "connect_code": f"P{index}#001",
                "display_name": f"P{index}",
                "tag": f"P{index}",
                "user_id": None,
                "is_winner": winner_flag,
            }
        )
    return ParsedReplayData(
        stage=31,
        start_time="2024-01-01T00:00:00Z",
        last_frame=last_frame,
        is_teams=0,
        players=players,
        peppi_bytes=b"x",
        end_method=end_method,
    )


def test_classify_early_no_contest_as_handwarmer():
    result = classify_handwarmer(_parsed(last_frame=2400, end_method="NO_CONTEST", winners=[None, None]))
    assert result.label == "handwarmer"
    assert result.reason == "early_no_contest"


def test_classify_short_unresolved_as_handwarmer():
    result = classify_handwarmer(_parsed(last_frame=2000, end_method="UNRESOLVED", winners=[None, None]))
    assert result.label == "handwarmer"
    assert result.reason in {"early_no_contest", "short_unresolved"}


def test_classify_real_when_game_has_winner_and_duration():
    result = classify_handwarmer(_parsed(last_frame=8000, end_method="GAME", winners=[1, 0]))
    assert result.label == "real"


def test_classify_unknown_without_parse_data():
    result = classify_handwarmer(None)
    assert result.label == "unknown"
    assert result.reason == "parse_failed"


def test_classify_insufficient_humans_as_handwarmer():
    parsed = _parsed(last_frame=600, end_method="UNRESOLVED", winners=[None])
    result = classify_handwarmer(parsed)
    assert result.label == "handwarmer"
    assert result.reason == "insufficient_humans"
