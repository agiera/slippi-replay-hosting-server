import { API_BASE } from "../../config/env.js";
import { clearSession, getAccessToken, getRefreshToken, persistSession } from "./session.js";

// Refresh this long before `exp` so a token doesn't lapse in flight.
const ACCESS_TOKEN_EXPIRY_SKEW_S = 30;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Serializes params, skipping null/undefined/"" so callers can pass filter
// objects straight through.
export function buildQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function apiUrl(path, query) {
  return `${API_BASE}${path}${buildQuery(query)}`;
}

// FastAPI errors come back as { detail: string } or, for validation errors,
// { detail: [{ msg, ... }] }.
async function extractErrorMessage(res) {
  try {
    const body = await res.json();
    if (Array.isArray(body?.detail)) {
      return body.detail.map((item) => item?.msg || String(item)).join("; ") || "Request failed";
    }
    return body?.detail || "Request failed";
  } catch {
    return "Request failed";
  }
}

// True when `token` is a JWT whose `exp` has passed; opaque tokens are left alone.
export function isAccessTokenExpired(token, nowMs = Date.now()) {
  const payload = String(token || "").split(".")[1];
  if (!payload) {
    return false;
  }
  try {
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const exp = Number(JSON.parse(json)?.exp);
    return Number.isFinite(exp) && exp - ACCESS_TOKEN_EXPIRY_SKEW_S <= nowMs / 1000;
  } catch {
    return false;
  }
}

let refreshInFlight = null;

/**
 * Exchanges the stored refresh token for a new session. Concurrent callers share
 * one request. A server rejection clears the session; network errors keep it.
 */
export function refreshAccessToken() {
  if (refreshInFlight) {
    return refreshInFlight;
  }
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return Promise.reject(new Error("No refresh token available"));
  }

  refreshInFlight = (async () => {
    try {
      const data = await request("/auth/refresh", {
        method: "POST",
        body: { refresh_token: refreshToken },
        auth: false,
      });
      persistSession(data);
      return data;
    } catch (err) {
      if (err instanceof ApiError) {
        clearSession();
      }
      throw err;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

/**
 * JSON request against the API. Sends the bearer token when one is stored
 * (unless `auth: false`) and throws ApiError with the server's detail on non-2xx.
 *
 * An expired access token is refreshed first: optional-auth endpoints treat a
 * stale token as anonymous and would otherwise silently drop private data.
 */
export async function request(path, { method = "GET", query, body, auth = true } = {}) {
  const headers = {};
  if (auth) {
    if (isAccessTokenExpired(getAccessToken()) && getRefreshToken()) {
      try {
        await refreshAccessToken();
      } catch {
        // Fall through: a rejected refresh cleared the session (anonymous request);
        // a network failure leaves the old token for the server to judge.
      }
    }
    const accessToken = getAccessToken();
    if (accessToken) {
      headers.Authorization = `Bearer ${accessToken}`;
    }
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(apiUrl(path, query), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    throw new ApiError(await extractErrorMessage(res), res.status);
  }
  if (res.status === 204) {
    return null;
  }
  return res.json();
}
