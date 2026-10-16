// URL builders for replay downloads, Slippi Dolphin deep links and SlippiLab.
import { API_BASE, SLIPPILAB_URL } from "../config/env.js";

export function buildApiUrl(pathname, { base = API_BASE, origin = globalThis.window?.location?.origin } = {}) {
  const normalizedBase = String(base || "").replace(/\/+$/, "");
  if (/^https?:\/\//i.test(normalizedBase)) {
    return new URL(`${normalizedBase}${pathname}`).toString();
  }
  return new URL(`${normalizedBase}${pathname}`, origin).toString();
}

export function buildReplayDownloadUrl(fileId, options) {
  if (!fileId) {
    return "";
  }
  return buildApiUrl(`/replays/files/${fileId}/download`, options);
}

// Prefers the server-provided download_url, falling back to the file id.
export function resolveReplayDownloadUrl(row, options) {
  if (row?.download_url) {
    return buildApiUrl(row.download_url, options);
  }
  return buildReplayDownloadUrl(row?.fileId ?? row?.id, options);
}

export function buildSlippiDeepLink(replayUrl) {
  if (!replayUrl) {
    return "";
  }
  return `slippi://play?path=${encodeURIComponent(replayUrl)}`;
}

export function buildLiveSourceDownloadUrl(sourceName, options) {
  const normalized = String(sourceName || "").trim();
  if (!normalized) {
    return "";
  }
  return buildApiUrl(`/replays/stream/sources/${encodeURIComponent(normalized)}/download`, options);
}

// Deep link that tells Slippi Dolphin to mirror a live source's in-progress replay.
export function buildSlippiMirrorDeepLink(sourceName, options) {
  const normalized = String(sourceName || "").trim();
  const liveUrl = buildLiveSourceDownloadUrl(normalized, options);
  if (!liveUrl) {
    return "";
  }
  return `slippi://play?path=${encodeURIComponent(liveUrl)}&mirror=1&console=${encodeURIComponent(normalized)}`;
}

export function buildSlippiLabViewerUrl(replayUrl, slippiLabUrl = SLIPPILAB_URL) {
  const replayTarget = String(replayUrl || "").trim();
  if (!replayTarget || !slippiLabUrl) {
    return "";
  }
  return `${slippiLabUrl}?replayUrl=${encodeURIComponent(replayTarget)}`;
}
