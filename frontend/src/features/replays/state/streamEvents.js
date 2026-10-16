// Decisions made for each `stream_event` SSE frame, kept pure so they can be tested.
import { isTerminalStreamStatus } from "./rowLifecycle.js";

function trimmed(value) {
  return String(value || "").trim();
}

// When a stream ends, its live row is kept on screen (as finalizing) until the
// replay list refresh brings in the completed file. Returns the row key to keep,
// or "" if this event doesn't end a stream.
export function getTerminalRowKey(payload) {
  if (!isTerminalStreamStatus(payload?.status)) {
    return "";
  }
  const streamGameId = trimmed(payload?.stream_game_id);
  if (streamGameId) {
    return `stream:${streamGameId}`;
  }
  const sourceName = trimmed(payload?.source_name);
  return sourceName ? `source:${sourceName}` : "";
}

// True when a newer game just started on the source the viewer is following in
// Slippi, so the mirror deep link should be re-fired.
export function shouldAdvanceMirror(payload, { followSource, lastMirroredGameId }) {
  const streamGameId = trimmed(payload?.stream_game_id);
  return (
    String(payload?.status || "").toLowerCase() === "started" &&
    Boolean(followSource) &&
    trimmed(payload?.source_name) === followSource &&
    Boolean(streamGameId) &&
    streamGameId !== lastMirroredGameId
  );
}
