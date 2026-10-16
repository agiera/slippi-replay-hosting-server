import { STAGE_NAME_BY_ID } from "../data/stages.js";

export function formatGameDuration(totalSeconds) {
  if (totalSeconds === null || totalSeconds === undefined) {
    return "-";
  }

  // e.g. "1m 30s".
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const minutesPart = Math.floor(seconds / 60);
  const secondsPart = seconds % 60;
  return `${minutesPart}m ${secondsPart}s`;
}

// e.g. "Mar 4, 2025 - 7:05pm" in the viewer's local time zone.
export function formatPlayedDateTime(value) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const month = date.toLocaleString("en-US", { month: "short" });
  const day = date.getDate();
  const year = date.getFullYear();
  let hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const period = hours >= 12 ? "pm" : "am";
  hours = hours % 12 || 12;

  return `${month} ${day}, ${year} - ${hours}:${minutes}${period}`;
}

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

// "Just now", "12 min ago", "3 hr ago", "Yesterday", "4 days ago", then a date
// ("Mar 4", or "Mar 4, 2024" outside the current year).
export function formatRelativeTime(value, nowMs) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const elapsedMs = Math.max(0, nowMs - date.getTime());
  if (elapsedMs < MINUTE_MS) {
    return "Just now";
  }
  if (elapsedMs < HOUR_MS) {
    return `${Math.floor(elapsedMs / MINUTE_MS)} min ago`;
  }
  if (elapsedMs < DAY_MS) {
    return `${Math.floor(elapsedMs / HOUR_MS)} hr ago`;
  }
  const days = Math.floor(elapsedMs / DAY_MS);
  if (days === 1) {
    return "Yesterday";
  }
  if (days < 7) {
    return `${days} days ago`;
  }

  const sameYear = date.getFullYear() === new Date(nowMs).getFullYear();
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

export function formatStageName(stageId) {
  if (stageId === null || stageId === undefined) {
    return "-";
  }

  const normalizedId = Number(stageId);
  if (Number.isNaN(normalizedId)) {
    return String(stageId);
  }

  return STAGE_NAME_BY_ID[normalizedId] || `Stage ${normalizedId}`;
}
