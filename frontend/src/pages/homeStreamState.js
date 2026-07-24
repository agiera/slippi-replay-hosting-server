import { normalizeStreamStatusPayload } from "../lib/api.js";

const REFRESH_STATUSES = new Set(["pending_parse", "slippi_file_metadata", "ended", "completed"]);

function getSourceKey(source) {
  const streamGameId = String(source?.stream_game_id || "").trim();
  if (streamGameId) {
    return `stream:${streamGameId}`;
  }

  const sourceName = String(source?.source_name || "").trim();
  return sourceName ? `source:${sourceName}` : "";
}

function getPreviewPlayerKey(player) {
  const connectCode = String(player?.connect_code || player?.slippi_code || "").trim().toUpperCase();
  const port = Number(player?.port);
  if (connectCode && Number.isFinite(port)) {
    return `${port}:${connectCode}`;
  }
  if (connectCode) {
    return `cc:${connectCode}`;
  }
  if (Number.isFinite(port)) {
    return `port:${port}`;
  }
  return "";
}

function mergePreviewPlayers(nextPlayers, prevPlayers) {
  const prevByKey = new Map();
  for (const player of prevPlayers) {
    const key = getPreviewPlayerKey(player);
    if (key) {
      prevByKey.set(key, player);
    }
  }

  return nextPlayers.map((player) => {
    const key = getPreviewPlayerKey(player);
    const prevPlayer = key ? prevByKey.get(key) : undefined;
    if (!prevPlayer) {
      return player;
    }

    return {
      ...player,
      rank: player?.rank ?? prevPlayer?.rank ?? null,
      rating: player?.rating ?? prevPlayer?.rating ?? null,
    };
  });
}

export function newestRefreshEventMs(events = []) {
  return (events || []).reduce((latest, event) => {
    const status = String(event?.status || "").toLowerCase();
    if (!REFRESH_STATUSES.has(status)) {
      return latest;
    }

    const ts = event?.timestamp ? new Date(event.timestamp).getTime() : NaN;
    if (Number.isNaN(ts)) {
      return latest;
    }

    return Math.max(latest, ts);
  }, 0);
}

export function shouldRefreshReplayList(events = [], latestCompletedEventMs = 0) {
  const newestMs = newestRefreshEventMs(events);
  return {
    shouldRefresh: newestMs > latestCompletedEventMs,
    newestMs,
  };
}

export function applySnapshotOrStatusFrame(prevState, payload) {
  const normalized = normalizeStreamStatusPayload(payload, Array.isArray(prevState?.events) ? prevState.events : []);

  const prevSources = Array.isArray(prevState?.sources) ? prevState.sources : [];
  const prevByKey = new Map(
    prevSources
      .map((source) => [getSourceKey(source), source])
      .filter(([key]) => Boolean(key))
  );

  const sources = (normalized.sources || []).map((source) => {
    const key = getSourceKey(source);
    if (!key) {
      return source;
    }

    const prevSource = prevByKey.get(key);
    if (!prevSource) {
      return source;
    }

    const nextPlayers = Array.isArray(source.player_preview) ? source.player_preview : [];
    const prevPlayers = Array.isArray(prevSource.player_preview) ? prevSource.player_preview : [];

    const mergedPlayers = mergePreviewPlayers(nextPlayers, prevPlayers);
    const nextRankReady = source.rank_lookup_complete;
    const mergedRankReady =
      nextRankReady === true || nextRankReady === false
        ? nextRankReady
        : (prevSource.rank_lookup_complete === true);

    return {
      ...source,
      rank_lookup_complete: mergedRankReady,
      player_preview: mergedPlayers,
    };
  });

  return {
    ...normalized,
    sources,
  };
}

export function applyStreamEventFrame(prevState, payload, { maxEvents = 200 } = {}) {
  const prevEvents = Array.isArray(prevState?.events) ? prevState.events : [];
  const nextEvents = [payload, ...prevEvents]
    .filter((row, index, rows) => {
      const id = Number(row?.event_id) || 0;
      if (!id) {
        return true;
      }
      return rows.findIndex((candidate) => (Number(candidate?.event_id) || 0) === id) === index;
    })
    .slice(0, maxEvents);

  return {
    tournament: prevState?.tournament || null,
    sources: Array.isArray(prevState?.sources) ? prevState.sources : [],
    events: nextEvents,
  };
}
