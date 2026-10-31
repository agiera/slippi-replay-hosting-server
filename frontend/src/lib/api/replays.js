import { request } from "./client.js";

// Query params accepted by GET /replays/files; anything else in `params` is ignored.
const REPLAY_FILE_QUERY_KEYS = [
  "limit",
  "cursor",
  "date_from",
  "date_to",
  "keyword",
  "character",
  "costume",
  "ranked",
  "rank",
  "min_rank",
  "max_rank",
  "player",
  "repository",
  "tournament",
  "source",
  "collection",
  "include_handwarmers",
];

export function fetchReplayFiles(params = {}) {
  const query = Object.fromEntries(REPLAY_FILE_QUERY_KEYS.map((key) => [key, params[key]]));
  return request("/replays/files", { query });
}

export function fetchReplayFilterOptions() {
  return request("/replays/filters");
}
