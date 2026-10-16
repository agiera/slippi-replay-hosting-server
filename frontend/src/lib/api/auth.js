import { ApiError, apiUrl, request } from "./client.js";
import { clearSession, getAccessToken, getRefreshToken, persistSession, storeUser } from "./session.js";

export function signup(payload) {
  return request("/auth/signup", { method: "POST", body: payload, auth: false });
}

export function login(payload) {
  return request("/auth/login", { method: "POST", body: payload, auth: false });
}

export async function refreshSession() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }

  let data;
  try {
    data = await request("/auth/refresh", {
      method: "POST",
      body: { refresh_token: refreshToken },
      auth: false,
    });
  } catch (err) {
    // Only a server rejection invalidates the session; keep it across network blips.
    if (err instanceof ApiError) {
      clearSession();
    }
    throw err;
  }

  persistSession(data);
  return data;
}

// Loads the current user, refreshing the access token once if it has expired.
export async function fetchMe() {
  if (!getAccessToken()) {
    throw new Error("No access token available");
  }

  let user;
  try {
    user = await request("/auth/me");
  } catch (err) {
    if (err?.status !== 401) {
      throw err;
    }
    await refreshSession();
    user = await request("/auth/me");
  }

  storeUser(user);
  return user;
}

// Revokes the refresh token server-side (best effort) and always clears the local session.
export async function logout() {
  const refreshToken = getRefreshToken();
  try {
    if (refreshToken) {
      await request("/auth/logout", { method: "POST", body: { refresh_token: refreshToken }, auth: false });
    }
  } catch {
    // The local session is cleared regardless.
  } finally {
    clearSession();
  }
}

export function getGoogleLoginUrl() {
  return apiUrl("/auth/google/login");
}
