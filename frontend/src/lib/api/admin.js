// Settings-page endpoints: the caller's API tokens plus superuser management of
// sources, tournament series, users and repositories.
import { request } from "./client.js";

// API tokens (sources)

export function listMyApiTokens() {
  return request("/users/me/api-tokens");
}

export function createMyApiToken(payload) {
  return request("/users/me/api-tokens", { method: "POST", body: payload });
}

export function revokeMyApiToken(tokenId) {
  return request(`/users/me/api-tokens/${tokenId}`, { method: "DELETE" });
}

export function listSources() {
  return request("/users/sources");
}

// Tournament series

export function listTournaments() {
  return request("/users/tournaments");
}

export function createTournament(payload) {
  return request("/users/tournaments", { method: "POST", body: payload });
}

export function updateTournament(tournamentId, payload) {
  return request(`/users/tournaments/${tournamentId}`, { method: "PATCH", body: payload });
}

export function getTournamentSourceIds(tournamentId) {
  return request(`/users/tournaments/${tournamentId}/sources`);
}

export function updateTournamentSources(tournamentId, sourceIds) {
  return request(`/users/tournaments/${tournamentId}/sources`, {
    method: "PUT",
    body: { source_ids: sourceIds },
  });
}

// Users and repositories

export function listUsers() {
  return request("/users");
}

export function updateUserRole(userId, role) {
  return request(`/users/${userId}/role`, { method: "PATCH", body: { role } });
}

export function updateUserRepositories(userId, repositoryIds) {
  return request(`/users/${userId}/repositories`, {
    method: "PUT",
    body: { repository_ids: repositoryIds },
  });
}

export function listRepositories() {
  return request("/users/repositories");
}

export function createRepository(name) {
  return request("/users/repositories", { method: "POST", body: { name } });
}
