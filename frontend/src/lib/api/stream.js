// Live stream endpoints. These are public, so no auth header is sent.
import { apiUrl, request } from "./client.js";

const STREAM_EVENT_TYPES = ["snapshot", "status", "stream_event", "heartbeat"];

export function listStreamTournaments() {
  return request("/replays/stream/tournaments", { auth: false });
}

export async function fetchStreamStatus(tournamentId) {
  const payload = await request("/replays/stream/status", {
    query: { tournament_id: tournamentId || undefined },
    auth: false,
  });
  return normalizeStreamStatusPayload(payload);
}

export function normalizeStreamEventPayload(payload) {
  const connectCode = payload?.connect_code || payload?.slippi_code || null;
  const name = payload?.display_name || payload?.name || connectCode || payload?.tag || null;
  return {
    ...payload,
    name,
    connect_code: connectCode,
    character_id: payload?.character_id ?? null,
    character_color: payload?.character_color ?? null,
    costume_id: payload?.costume_id ?? null,
    port: payload?.port ?? null,
    type: payload?.type ?? null,
    is_cpu: Boolean(payload?.is_cpu),
    is_winner: payload?.is_winner ?? null,
    rank: payload?.rank ?? null,
    rating: payload?.rating ?? null,
  };
}

export function normalizeStreamStatusPayload(payload, fallbackEvents = []) {
  const normalizedSources = (Array.isArray(payload?.sources) ? payload.sources : []).map((source) => {
    const normalizedPreview = (Array.isArray(source?.player_preview) ? source.player_preview : []).map(
      normalizeStreamEventPayload,
    );

    return {
      ...source,
      player_preview: normalizedPreview,
    };
  });

  return {
    tournament: payload?.tournament || null,
    sources: normalizedSources,
    events: Array.isArray(payload?.events) ? payload.events : fallbackEvents,
  };
}

// Opens the SSE feed; `onEvent` receives every frame type. Caller owns close().
export function openStreamEvents(onEvent, { tournamentId } = {}) {
  const url = new URL(
    apiUrl("/replays/stream/events", { tournament_id: tournamentId || undefined }),
    window.location.origin,
  ).toString();
  const eventSource = new EventSource(url);

  if (typeof onEvent === "function") {
    STREAM_EVENT_TYPES.forEach((type) => eventSource.addEventListener(type, onEvent));
  }

  return eventSource;
}
