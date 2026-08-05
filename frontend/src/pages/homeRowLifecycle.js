const TERMINAL_STREAM_PHASES = new Set(["ended", "completed", "abandoned", "incomplete", "failed"]);
const FINALIZING_STREAM_PHASES = new Set(["pending_parse", "slippi_file_metadata"]);

function isTerminalStreamStatus(status) {
  return TERMINAL_STREAM_PHASES.has(String(status || "").toLowerCase());
}

function isFinalizingStreamStatus(status) {
  return FINALIZING_STREAM_PHASES.has(String(status || "").toLowerCase());
}

function isActivelyStreaming(source) {
  if (!source?.connected) {
    return false;
  }

  const phase = String(source?.stream_phase || "").toLowerCase();
  if (isTerminalStreamStatus(phase) || isFinalizingStreamStatus(phase)) {
    return false;
  }

  return true;
}

function getStreamSessionKey(row) {
  const streamGameId = String(row?.stream_game_id || "").trim();
  if (streamGameId) {
    return `stream:${streamGameId}`;
  }

  const sourceName = String(row?.source_name || "").trim();
  if (sourceName) {
    return `source:${sourceName}`;
  }

  return "";
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

function isLiveSourceRankReady(source) {
  if (source?.rank_lookup_complete === true) {
    return true;
  }
  if (source?.rank_lookup_complete === false) {
    return false;
  }

  const players = Array.isArray(source?.player_preview) ? source.player_preview : [];
  if (players.length === 0) {
    return false;
  }

  return players.every((player) => {
    if (!player || typeof player !== "object") {
      return true;
    }

    const isCpu = Boolean(player.is_cpu) || Number(player.type) === 1;
    if (isCpu) {
      return true;
    }

    const connectCode = String(player.connect_code || player.slippi_code || "").trim();
    if (!connectCode) {
      return true;
    }

    return player.rank != null || player.rating != null;
  });
}

function isLiveSourceVisible(source, streamEvents, completedFiles, nowMs, preservedTerminalRowKeys) {
  const streamSessionKey = getStreamSessionKey(source);
  const preserveTerminalRow = streamSessionKey && preservedTerminalRowKeys.has(streamSessionKey);

  if (isTerminalStreamStatus(source.stream_phase) && !preserveTerminalRow) {
    return false;
  }

  const sourceLastActivityMs = source.last_activity_at
    ? new Date(source.last_activity_at).getTime()
    : (source.updated_at ? new Date(source.updated_at).getTime() : NaN);
  if (!source.connected && !Number.isNaN(sourceLastActivityMs)) {
    const staleDisconnectedWindowMs = 2 * 60 * 1000;
    if (nowMs - sourceLastActivityMs > staleDisconnectedWindowMs) {
      return false;
    }
  }

  if (!Array.isArray(source.player_preview) || source.player_preview.length === 0) {
    return false;
  }

  if (!isLiveSourceRankReady(source)) {
    return false;
  }

  const sourceName = (source.source_name || "").trim();
  if (!sourceName) {
    return false;
  }

  const sourceStreamGameId = String(source.stream_game_id || "").trim();

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

  if (terminalEventForSession && !preserveTerminalRow) {
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

function hasTerminalEventForSession(source, streamEvents) {
  const sourceName = (source?.source_name || "").trim();
  const sourceStreamGameId = String(source?.stream_game_id || "").trim();
  const connectedAtMs = source?.connected_at ? new Date(source.connected_at).getTime() : NaN;

  return (streamEvents || []).some((event) => {
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
}

function toLiveReplayRow(source, nowMs, tournament, terminalEventForSession = false) {
  const players = Array.isArray(source.player_preview) ? source.player_preview : [];
  const activelyStreaming = isActivelyStreaming(source) && !terminalEventForSession;
  const connectedAtMs = source.connected_at ? new Date(source.connected_at).getTime() : NaN;
  const updatedAtMs = source.updated_at ? new Date(source.updated_at).getTime() : NaN;
  const lastActivityAtMs = source.last_activity_at ? new Date(source.last_activity_at).getTime() : NaN;
  const endAtMs = !Number.isNaN(lastActivityAtMs)
    ? lastActivityAtMs
    : updatedAtMs;
  const durationBaseMs = !Number.isNaN(connectedAtMs)
    ? connectedAtMs
    : (!Number.isNaN(updatedAtMs) ? updatedAtMs : lastActivityAtMs);
  const durationNowMs = activelyStreaming ? nowMs : endAtMs;
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
    lifecycle: activelyStreaming ? "live" : "finalizing",
    rowKey: source.stream_game_id
      ? `stream:${source.stream_game_id}`
      : `live:${sourceName}:${source.username || "unknown"}`,
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
    source_label: sourceName || "-",
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
    rowKey: file.stream_game_id
      ? `stream:${file.stream_game_id}`
      : `file:${fileId || fallbackKey}`,
    fileId,
    source_name: sourceName,
    start_datetime: file.datetime_played || file.birth_time || null,
    resolved_tournament_name: resolvedTournamentName,
    repository_label: resolvedTournamentName || folderMeta.repository || "-",
    source_label: sourceName || "-",
  };
}

export function mergeReplayRows({
  streamStatus,
  files,
  nowMs,
  includeLiveRows = true,
  preservedTerminalRows = [],
}) {
  const preservedTerminalRowKeys = new Set(preservedTerminalRows);
  const completedRows = (files || []).map((file) => toCompletedReplayRow(file));
  const completedByStreamGameId = new Map(
    completedRows
      .map((row) => [String(row.stream_game_id || "").trim(), row])
      .filter(([streamGameId]) => Boolean(streamGameId))
  );

  const liveRows = includeLiveRows
    ? (streamStatus.sources || [])
        .filter((source) => isLiveSourceVisible(source, streamStatus.events, files, nowMs, preservedTerminalRowKeys))
        .map((source) => {
          const terminalEventForSession = hasTerminalEventForSession(source, streamStatus.events);
          return toLiveReplayRow(source, nowMs, streamStatus.tournament, terminalEventForSession);
        })
    : [];

  const usedCompletedStreamGameIds = new Set();
  const mergedRows = liveRows.map((row) => {
    const streamGameId = String(row.stream_game_id || "").trim();
    if (!streamGameId) {
      return row;
    }

    const completedRow = completedByStreamGameId.get(streamGameId);
    if (!completedRow) {
      return row;
    }

    usedCompletedStreamGameIds.add(streamGameId);
    return completedRow;
  });

  const trailingCompletedRows = completedRows.filter((row) => {
    const streamGameId = String(row.stream_game_id || "").trim();
    return !streamGameId || !usedCompletedStreamGameIds.has(streamGameId);
  });

  return [...mergedRows, ...trailingCompletedRows];
}
