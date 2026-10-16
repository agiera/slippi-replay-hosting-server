import { API_BASE } from "../../config/env.js";
import { getAccessToken } from "./session.js";

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

/**
 * JSON request against the API. Sends the bearer token when one is stored
 * (unless `auth: false`) and throws ApiError with the server's detail on non-2xx.
 */
export async function request(path, { method = "GET", query, body, auth = true } = {}) {
  const headers = {};
  if (auth) {
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
