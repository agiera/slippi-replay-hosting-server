import { useCallback, useEffect, useRef, useState } from "react";

import { fetchStreamStatus, openStreamEvents } from "../../../lib/api/stream";
import { buildSlippiMirrorDeepLink } from "../../../lib/links";
import { getTerminalRowKey, shouldAdvanceMirror } from "../state/streamEvents";
import { createStreamStatusRefreshScheduler } from "../state/streamRefresh";
import {
  applySnapshotOrStatusFrame,
  applyStreamEventFrame,
  shouldRefreshReplayList,
} from "../state/streamState";

const EMPTY_STREAM_STATUS = { tournament: null, sources: [], events: [] };

/**
 * Live stream state from REST + SSE, plus "follow in Slippi": once the viewer
 * mirrors a source, each newer game on that source re-fires the mirror link.
 *
 * @param onReplaysChanged called when a stream finished and the replay list should reload
 * @param onTerminalRow    called with a row key to keep visible after its stream ends
 */
export function useLiveStream({ onReplaysChanged, onTerminalRow }) {
  const [streamStatus, setStreamStatus] = useState(EMPTY_STREAM_STATUS);
  const [streamError, setStreamError] = useState("");
  const [followSource, setFollowSource] = useState("");
  // The SSE handler lives for the whole mount, so it reads these through refs.
  const followSourceRef = useRef("");
  const lastMirroredGameIdRef = useRef("");
  const latestCompletedEventMsRef = useRef(0);
  const callbacksRef = useRef({ onReplaysChanged, onTerminalRow });

  useEffect(() => {
    callbacksRef.current = { onReplaysChanged, onTerminalRow };
  }, [onReplaysChanged, onTerminalRow]);

  useEffect(() => {
    let active = true;

    async function refreshStreamStatus() {
      try {
        const statusPayload = await fetchStreamStatus();
        if (!active) {
          return;
        }
        setStreamStatus((prev) => applySnapshotOrStatusFrame(prev, statusPayload));
      } catch {
        // Keep the existing SSE-driven state when status fetch fails.
      }
    }

    const streamStatusRefreshScheduler = createStreamStatusRefreshScheduler({
      delayMs: 250,
      onRefresh: refreshStreamStatus,
    });

    // Paint live rows from REST right away instead of waiting on the first SSE
    // snapshot frame, which can lag behind a proxy/loaded backend.
    void refreshStreamStatus();

    function maybeRefreshReplayList(events) {
      const refresh = shouldRefreshReplayList(events, latestCompletedEventMsRef.current);
      if (refresh.shouldRefresh) {
        latestCompletedEventMsRef.current = refresh.newestMs;
        void callbacksRef.current.onReplaysChanged?.();
      }
    }

    function handleStatusFrame(event) {
      try {
        const payload = JSON.parse(event.data || "{}");
        setStreamStatus((prev) => applySnapshotOrStatusFrame(prev, payload));
        streamStatusRefreshScheduler.schedule();
        setStreamError("");
        if (event.type === "snapshot") {
          maybeRefreshReplayList(payload?.events || []);
        }
      } catch {
        setStreamError("Failed to parse stream status update");
      }
    }

    function handleStreamEvent(event) {
      try {
        const payload = JSON.parse(event.data || "{}");
        setStreamStatus((prev) => applyStreamEventFrame(prev, payload));

        const follow = {
          followSource: followSourceRef.current,
          lastMirroredGameId: lastMirroredGameIdRef.current,
        };
        if (shouldAdvanceMirror(payload, follow)) {
          const mirrorLink = buildSlippiMirrorDeepLink(follow.followSource);
          if (mirrorLink) {
            lastMirroredGameIdRef.current = String(payload.stream_game_id).trim();
            window.location.href = mirrorLink;
          }
        }

        const terminalRowKey = getTerminalRowKey(payload);
        if (terminalRowKey) {
          callbacksRef.current.onTerminalRow?.(terminalRowKey);
        }

        // Some environments intermittently miss `status` frames while still
        // receiving `stream_event`. Re-sync sources from the status endpoint
        // on each event so live rows appear/update without manual refresh.
        streamStatusRefreshScheduler.schedule();
        setStreamError("");
        maybeRefreshReplayList([payload]);
      } catch {
        setStreamError("Failed to parse stream event update");
      }
    }

    const stream = openStreamEvents((event) => {
      if (!active) {
        return;
      }
      if (event.type === "snapshot" || event.type === "status") {
        handleStatusFrame(event);
      } else if (event.type === "stream_event") {
        handleStreamEvent(event);
      }
    });

    stream.onerror = () => {
      if (active) {
        setStreamError("Stream updates disconnected. Reconnecting...");
      }
    };

    return () => {
      active = false;
      streamStatusRefreshScheduler.cancel();
      stream.close();
    };
  }, []);

  // Opens the source in Slippi's mirror mode and keeps following it.
  const followInSlippi = useCallback((sourceName, streamGameId) => {
    const normalizedSource = String(sourceName || "").trim();
    if (!normalizedSource) {
      return;
    }

    const slippiLink = buildSlippiMirrorDeepLink(normalizedSource);
    if (!slippiLink) {
      setStreamError(`No replay available yet for source ${normalizedSource}.`);
      return;
    }
    // Remember which game we're launching so the SSE handler only auto-advances
    // when a *newer* game from this same source begins.
    lastMirroredGameIdRef.current = String(streamGameId || "").trim();
    followSourceRef.current = normalizedSource;
    setFollowSource(normalizedSource);
    setStreamError("");
    window.location.href = slippiLink;
  }, []);

  const stopFollowing = useCallback(() => {
    followSourceRef.current = "";
    lastMirroredGameIdRef.current = "";
    setFollowSource("");
  }, []);

  return { streamStatus, streamError, followSource, followInSlippi, stopFollowing };
}
