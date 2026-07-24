import { normalizeStreamStatusPayload } from "../lib/api.js";

const REFRESH_STATUSES = new Set(["pending_parse", "slippi_file_metadata", "ended", "completed"]);

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
  return normalizeStreamStatusPayload(payload, Array.isArray(prevState?.events) ? prevState.events : []);
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
