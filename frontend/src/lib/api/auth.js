import { apiUrl, refreshAccessToken, request } from "./client.js";
import { clearSession, getAccessToken, getRefreshToken, storeUser } from "./session.js";

export function signup(payload) {
  return request("/auth/signup", { method: "POST", body: payload, auth: false });
}

export function login(payload) {
  return request("/auth/login", { method: "POST", body: payload, auth: false });
}

export function refreshSession() {
  return refreshAccessToken();
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
