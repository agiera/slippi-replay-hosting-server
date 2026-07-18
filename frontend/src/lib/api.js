const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

const ACCESS_TOKEN_KEY = "token";
const REFRESH_TOKEN_KEY = "refresh_token";
const USER_KEY = "user";

export async function signup(payload) {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function login(payload) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export function persistSession({ access_token, refresh_token, user }) {
  localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new Event("auth:changed"));
}

export function clearSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event("auth:changed"));
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

export async function refreshSession() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }

  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) {
    clearSession();
    throw new Error(await extractError(res));
  }

  const data = await res.json();
  persistSession(data);
  return data;
}

export async function fetchMe() {
  let accessToken = getAccessToken();
  if (!accessToken) {
    throw new Error("No access token available");
  }

  let res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (res.status === 401) {
    const refreshed = await refreshSession();
    accessToken = refreshed.access_token;
    res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  }

  if (!res.ok) {
    throw new Error(await extractError(res));
  }

  const user = await res.json();
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  return user;
}

export async function logout() {
  const refreshToken = getRefreshToken();
  if (refreshToken) {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  }
  clearSession();
}

export async function fetchReplayFiles(params = {}) {
  const search = new URLSearchParams();

  if (params.limit) search.set("limit", String(params.limit));
  if (params.cursor) search.set("cursor", String(params.cursor));
  if (params.date_from) search.set("date_from", params.date_from);
  if (params.date_to) search.set("date_to", params.date_to);
  if (params.keyword) search.set("keyword", params.keyword);
  if (params.character) search.set("character", params.character);
  if (params.ranked !== undefined && params.ranked !== null && params.ranked !== "") {
    search.set("ranked", String(params.ranked));
  }
  if (params.rank) search.set("rank", params.rank);
  if (params.min_rank) search.set("min_rank", params.min_rank);
  if (params.max_rank) search.set("max_rank", params.max_rank);
  if (params.player) search.set("player", params.player);
  if (params.repository) search.set("repository", params.repository);
  if (params.tournament) search.set("tournament", params.tournament);
  if (params.source) search.set("source", params.source);
  if (params.collection) search.set("collection", params.collection);

  const url = `${API_BASE}/replays/files${search.toString() ? `?${search.toString()}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function fetchReplayFilterOptions() {
  const res = await fetch(`${API_BASE}/replays/filters`);
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function listStreamTournaments() {
  const res = await fetch(`${API_BASE}/replays/stream/tournaments`);
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function fetchStreamStatus(tournamentId) {
  const search = new URLSearchParams();
  if (tournamentId) {
    search.set("tournament_id", String(tournamentId));
  }
  const url = `${API_BASE}/replays/stream/status${search.toString() ? `?${search.toString()}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export function openStreamEvents(onEvent, { tournamentId } = {}) {
  const search = new URLSearchParams();
  if (tournamentId) {
    search.set("tournament_id", String(tournamentId));
  }

  const rawUrl = `${API_BASE}/replays/stream/events${search.toString() ? `?${search.toString()}` : ""}`;
  const url = new URL(rawUrl, window.location.origin).toString();
  const eventSource = new EventSource(url);

  if (typeof onEvent === "function") {
    eventSource.addEventListener("snapshot", onEvent);
    eventSource.addEventListener("stream_event", onEvent);
    eventSource.addEventListener("heartbeat", onEvent);
  }

  return eventSource;
}

export async function listMyApiTokens() {
  const res = await fetch(`${API_BASE}/users/me/api-tokens`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function createMyApiToken(payload) {
  const res = await fetch(`${API_BASE}/users/me/api-tokens`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function listSources() {
  const res = await fetch(`${API_BASE}/users/sources`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function listTournaments() {
  const res = await fetch(`${API_BASE}/users/tournaments`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function createTournament(payload) {
  const res = await fetch(`${API_BASE}/users/tournaments`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function updateTournament(tournamentId, payload) {
  const res = await fetch(`${API_BASE}/users/tournaments/${tournamentId}`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function getTournamentSourceIds(tournamentId) {
  const res = await fetch(`${API_BASE}/users/tournaments/${tournamentId}/sources`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function updateTournamentSources(tournamentId, sourceIds) {
  const res = await fetch(`${API_BASE}/users/tournaments/${tournamentId}/sources`, {
    method: "PUT",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ source_ids: sourceIds }),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function revokeMyApiToken(tokenId) {
  const res = await fetch(`${API_BASE}/users/me/api-tokens/${tokenId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function listUsers() {
  const res = await fetch(`${API_BASE}/users`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function updateUserRole(userId, role) {
  const res = await fetch(`${API_BASE}/users/${userId}/role`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function listRepositories() {
  const res = await fetch(`${API_BASE}/users/repositories`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function createRepository(name) {
  const res = await fetch(`${API_BASE}/users/repositories`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

export async function updateUserRepositories(userId, repositoryIds) {
  const res = await fetch(`${API_BASE}/users/${userId}/repositories`, {
    method: "PUT",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ repository_ids: repositoryIds }),
  });
  if (!res.ok) {
    throw new Error(await extractError(res));
  }
  return res.json();
}

function extractError(res) {
  return res.json().then((body) => body.detail || "Request failed").catch(() => "Request failed");
}

function authHeaders() {
  const accessToken = getAccessToken();
  if (!accessToken) {
    return {};
  }
  return { Authorization: `Bearer ${accessToken}` };
}

export function getGoogleLoginUrl() {
  return `${API_BASE}/auth/google/login`;
}
