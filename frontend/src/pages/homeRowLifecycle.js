const TERMINAL_STREAM_PHASES = new Set(["ended", "completed", "abandoned", "incomplete", "failed"]);

function isTerminalStreamStatus(status) {
  return TERMINAL_STREAM_PHASES.has(String(status || "").toLowerCase());
}

function parseFolderMetadata(folder) {
  if (!folder) {
    return { repository: null, source: null };
  }

  const parts = String(folder)
    .split("/")
    .filter(Boolean);
  if (parts.length === 0) {
    return { repository: null, source: null };
  }

  if (parts[0] === "uploads") {
    const repository = parts[1] || null;
    let source = null;
    if (parts[2]) {
      const maybeSource = parts[2];
      if (!(maybeSource.length === 4 && /^\d+$/.test(maybeSource))) {
        source = maybeSource;
      }
    }
    return { repository, source };
  }

  return {
    repository: parts[0] || null,
    source: parts[1] || null,
  };
}

function getResolvedTournamentName(file) {
  return (
    file?.resolved_tournament_name ||
    file?.current_tournament_name ||
    file?.tournament_name ||
    file?.tournament ||
    null
  );
}

function isLiveSourceVisible(source, streamEvents, completedFiles, nowMs) {
  if (isTerminalStreamStatus(source.stream_phase)) {
    return false;
  }

  const sourceLastActivityMs = source.last_activity_at
    ? new Date(source.last_activity_at).getTime()
    : (source.updated_at ? new Date(source.updated_at).getTime() : NaN);
  if (!Number.isNaN(sourceLastActivityMs)) {
    const staleDisconnectedWindowMs = 2 * 60 * 1000;
    if (nowMs - sourceLastActivityMs > staleDisconnectedWindowMs) {
      return false;
    }
  }

  if (!Array.isArray(source.player_preview) || source.player_preview.length === 0) {
    return false;
  }

  const sourceName = (source.source_name || "").trim();
  if (!sourceName) {
    return false;
  }

  const sourceStreamGameId = String(source.stream_game_id || "").trim();

  if (sourceStreamGameId) {
    const hasFinalizedRowByKey = (completedFiles || []).some(
      (file) => String(file?.stream_game_id || "").trim() === sourceStreamGameId
    );
    if (hasFinalizedRowByKey) {
      return false;
    }
  }

  const connectedAtMs = source.connected_at ? new Date(source.connected_at).getTime() : NaN;
  const terminalEventForSession = (streamEvents || []).some((event) => {
    const eventStreamGameId = String(event?.stream_game_id || "").trim();
    if (sourceStreamGameId && eventStreamGameId) {
      if (eventStreamGameId !== sourceStreamGameId) {
        return false;
      }
    } else if ((event?.source_name || "").trim() !== sourceName) {
      return false;
    }

    if (!isTerminalStreamStatus(event?.status)) {
      return false;
    }

    if (Number.isNaN(connectedAtMs)) {
      return true;
    }

    const eventMs = event?.timestamp ? new Date(event.timestamp).getTime() : NaN;
    return !Number.isNaN(eventMs) && eventMs >= connectedAtMs - 5000;
  });

  if (terminalEventForSession) {
    return false;
  }

  const hasFinalizedRowForSession = (completedFiles || []).some((file) => {
    const fileSource = (file?.source_name || file?.collection_name || "").trim();
    if (!fileSource || fileSource !== sourceName) {
      return false;
    }

    if (Number.isNaN(connectedAtMs)) {
      return true;
    }

    const birthMs = file?.birth_time ? new Date(file.birth_time).getTime() : NaN;
    if (Number.isNaN(birthMs)) {
      return false;
    }

    return birthMs >= connectedAtMs - 5000;
  });

  return !hasFinalizedRowForSession;
}

function toLiveReplayRow(source, nowMs, tournament) {
  const players = Array.isArray(source.player_preview) ? source.player_preview : [];
  const connectedAtMs = source.connected_at ? new Date(source.connected_at).getTime() : NaN;
  const updatedAtMs = source.updated_at ? new Date(source.updated_at).getTime() : NaN;
  const lastActivityAtMs = source.last_activity_at ? new Date(source.last_activity_at).getTime() : NaN;
  const endAtMs = !Number.isNaN(lastActivityAtMs)
    ? lastActivityAtMs
    : updatedAtMs;
  const durationBaseMs = !Number.isNaN(connectedAtMs)
    ? connectedAtMs
    : (!Number.isNaN(updatedAtMs) ? updatedAtMs : lastActivityAtMs);
  const durationNowMs = source.connected ? nowMs : endAtMs;
  const playedAt = source.connected_at || source.updated_at || source.last_activity_at || null;
  const gameDuration = Number.isNaN(durationBaseMs) || Number.isNaN(durationNowMs)
    ? 0
    : Math.max(0, Math.floor((durationNowMs - durationBaseMs) / 1000));
  const sourceName = (source.source_name || "").trim();
  const resolvedTournamentName =
    source.resolved_tournament_name ||
    tournament?.current_tournament_name ||
    tournament?.name ||
    tournament?.repository_name ||
    null;

  return {
    ...source,
    lifecycle: source.connected ? "live" : "finalizing",
    rowKey: `live:${source.stream_game_id || `${sourceName}:${source.username || "unknown"}`}`,
    id: null,
    fileId: null,
    players,
    stage: source.stage_preview ?? null,
    game_duration: gameDuration,
    datetime_played: playedAt,
    start_datetime: playedAt,
    source_name: sourceName,
    stream_source_name: sourceName,
    stream_repositories: source.repositories || [],
    resolved_tournament_name: resolvedTournamentName,
    repository_label: resolvedTournamentName || source.repositories?.[0] || "Streaming",
    source_label: source.connected ? "Live stream" : "Finalizing upload",
    name: `live:${sourceName}`,
  };
}

function toCompletedReplayRow(file) {
  const folderMeta = parseFolderMetadata(file.folder);
  const resolvedTournamentName = getResolvedTournamentName(file);
  const sourceName = file.source_name || file.collection_name || folderMeta.source || null;
  const fileId = file.id ?? file._id ?? null;
  const fallbackKey = `${file.name}-${file.datetime_played || file.birth_time || "unknown"}`;

  return {
    ...file,
    lifecycle: "completed",
    rowKey: `file:${fileId || fallbackKey}`,
    fileId,
    source_name: sourceName,
    start_datetime: file.datetime_played || file.birth_time || null,
    resolved_tournament_name: resolvedTournamentName,
    repository_label: resolvedTournamentName || folderMeta.repository || "-",
    source_label: sourceName || "-",
  };
}

export function mergeReplayRows({ streamStatus, files, nowMs }) {
  const completedRows = (files || []).map((file) => toCompletedReplayRow(file));
  const completedByStreamGameId = new Set(
    completedRows
      .map((row) => String(row.stream_game_id || "").trim())
      .filter(Boolean)
  );

  const liveRows = (streamStatus.sources || [])
    .filter((source) => isLiveSourceVisible(source, streamStatus.events, files, nowMs))
    .map((source) => toLiveReplayRow(source, nowMs, streamStatus.tournament))
    .filter((row) => {
      const streamGameId = String(row.stream_game_id || "").trim();
      return !streamGameId || !completedByStreamGameId.has(streamGameId);
    });

  return [...liveRows, ...completedRows];
}
