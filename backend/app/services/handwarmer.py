from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.peppi_ingest import ParsedReplayData


HandwarmerLabel = Literal["real", "handwarmer", "unknown"]


@dataclass(frozen=True)
class HandwarmerClassification:
    label: HandwarmerLabel
    reason: str | None
    score: float | None
    version: int = 1


def classify_handwarmer(parsed_replay: ParsedReplayData | None) -> HandwarmerClassification:
    """Classify likely handwarmers from stable ingest-time replay signals.

    This intentionally uses conservative, low-risk heuristics available in the
    current parse pipeline: game end method, duration, player roster and winner
    resolution state.
    """
    if parsed_replay is None:
        return HandwarmerClassification(label="unknown", reason="parse_failed", score=None)

    human_players = [p for p in parsed_replay.players if int(p.get("type") or 0) == 0]
    if len(human_players) < 2:
        # Single-human / missing-opponent uploads are not complete matches and
        # should be hidden by default the same way as other warmup/aborted games.
        return HandwarmerClassification(label="handwarmer", reason="insufficient_humans", score=0.95)

    duration_seconds = None
    if parsed_replay.last_frame is not None:
        try:
            duration_seconds = max(0, int(parsed_replay.last_frame) // 60)
        except (TypeError, ValueError):
            duration_seconds = None

    winners = [p for p in human_players if p.get("is_winner") == 1]
    has_winner = len(winners) > 0
    end_method = (parsed_replay.end_method or "").upper()

    if duration_seconds is not None and end_method in {"NO_CONTEST", "UNRESOLVED"} and duration_seconds < 60:
        return HandwarmerClassification(label="handwarmer", reason="early_no_contest", score=0.98)

    if duration_seconds is not None and duration_seconds < 45 and not has_winner:
        return HandwarmerClassification(label="handwarmer", reason="short_unresolved", score=0.9)

    if duration_seconds is not None and duration_seconds < 30:
        return HandwarmerClassification(label="handwarmer", reason="ultra_short", score=0.8)

    if duration_seconds is None:
        return HandwarmerClassification(label="unknown", reason="missing_duration", score=None)

    return HandwarmerClassification(label="real", reason="duration_or_winner", score=0.8)
