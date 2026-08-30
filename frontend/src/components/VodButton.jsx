import { useEffect, useRef, useState } from "react";

import {
  buildRenderVodUrl,
  createRenderJob,
  getRenderJobForFile,
  getStoredUser,
  openRenderJobEvents,
} from "../lib/api";

const ACTIVE_STATUSES = new Set(["pending", "dispatched", "rendering"]);
const STARTED_STATUSES = new Set(["dispatched", "rendering"]);

function isPlayable(job) {
  // The worker streams a progressively-playable fragmented mp4, so the VOD is
  // watchable as soon as any output exists — even before the render finishes.
  return Boolean(job && job.has_output);
}

function isStarted(job) {
  return Boolean(job && STARTED_STATUSES.has(job.status));
}

function isQueued(job) {
  return Boolean(job && job.status === "pending");
}

function isActive(job) {
  return Boolean(job && ACTIVE_STATUSES.has(job.status));
}

function isFailed(job) {
  return Boolean(job && job.status === "failed");
}

export default function VodButton({ fileId, isPublic = false }) {
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const streamRef = useRef(null);
  const mountedRef = useRef(true);
  const loggedIn = Boolean(getStoredUser());

  function closeStream() {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
  }

  function watchJob(jobId) {
    closeStream();
    streamRef.current = openRenderJobEvents(jobId, (latest) => {
      if (!mountedRef.current) {
        return;
      }
      setJob(latest);
      if (!isActive(latest)) {
        closeStream();
      }
    });
  }

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;

    async function loadInitial() {
      if (!fileId) {
        return;
      }
      try {
        const existing = await getRenderJobForFile(fileId);
        if (cancelled || !mountedRef.current) {
          return;
        }
        setJob(existing);
        if (isActive(existing)) {
          watchJob(existing.id);
        }
      } catch {
        // Ignore lookup failures; the button falls back to "Request VOD".
      }
    }

    loadInitial();

    return () => {
      cancelled = true;
      mountedRef.current = false;
      closeStream();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId]);

  async function requestVod() {
    if (!fileId || busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const created = await createRenderJob(fileId);
      if (!mountedRef.current) {
        return;
      }
      setJob(created);
      if (isActive(created)) {
        watchJob(created.id);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || "Failed to request VOD");
      }
    } finally {
      if (mountedRef.current) {
        setBusy(false);
      }
    }
  }

  if (isPlayable(job)) {
    return (
      <a
        className="viewer-row-btn"
        href={buildRenderVodUrl(job.id)}
        target="_blank"
        rel="noopener noreferrer"
      >
        Play VOD
      </a>
    );
  }

  if (isQueued(job) || busy) {
    return (
      <button type="button" className="viewer-row-btn viewer-row-btn-secondary" disabled>
        Queued
      </button>
    );
  }

  if (isStarted(job)) {
    return (
      <button type="button" className="viewer-row-btn viewer-row-btn-secondary" disabled>
        Rendering...
      </button>
    );
  }

  if (!loggedIn && !isPublic) {
    return null;
  }

  // A server-side failed render is retryable, so it shows "Retry VOD" with the
  // failure reason rather than looking like a never-requested row.
  const failed = isFailed(job);
  const tooltip = error || (failed ? job.error || "Render failed" : undefined);

  return (
    <button
      type="button"
      className="viewer-row-btn"
      onClick={requestVod}
      title={tooltip}
    >
      {error || failed ? "Retry VOD" : "Request VOD"}
    </button>
  );
}
