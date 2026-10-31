import { CHARACTER_BY_ID } from "../../data/characters.js";

// Returns the players for a row, sorted by port. Both live-stream rows and
// completed replay rows expose a normalized `players` array, so this is the
// single source of truth the table renders from. The player_1_info/player_2_info
// pair is only a legacy fallback for rows missing the array.
export function getRowPlayers(file) {
  const players = Array.isArray(file?.players) ? file.players : [];
  const normalized = players
    .filter((player) => player && typeof player === "object")
    .slice()
    .sort((a, b) => {
      const pa = Number(a?.port);
      const pb = Number(b?.port);
      if (!Number.isFinite(pa) && !Number.isFinite(pb)) return 0;
      if (!Number.isFinite(pa)) return 1;
      if (!Number.isFinite(pb)) return -1;
      return pa - pb;
    });

  if (normalized.length > 0) {
    return normalized;
  }

  return [
    file?.player_1_info ? { ...file.player_1_info, name: file.player_1_info.name || file.player_1 } : null,
    file?.player_2_info ? { ...file.player_2_info, name: file.player_2_info.name || file.player_2 } : null,
  ].filter(Boolean);
}

// Display fields for a player cell, with the same fallbacks for live and completed rows.
export function getPlayerDisplay(player) {
  return {
    displayName: player.display_name || player.name || player.connect_code || player.tag || "-",
    connectCode: player.connect_code || "-",
    rating: player.rating ?? "--",
    isWinner: player.is_winner === 1,
    isCpu: Boolean(player.is_cpu) || Number(player.type) === 1,
  };
}

// Details shown in a player's tooltip. Missing values are null.
export function getPlayerDetails(player) {
  const { displayName, isCpu } = getPlayerDisplay(player);
  const port = Number(player.port);
  return {
    name: isCpu && displayName === "-" ? "CPU" : displayName,
    isCpu,
    character: CHARACTER_BY_ID.get(Number(player.character_id))?.name ?? null,
    connectCode: isCpu ? null : player.connect_code || null,
    port: port >= 1 && port <= 4 ? port : null,
    rankName: player.rank ? String(player.rank).replace(/_/g, " ") : null,
    rating: player.rating ?? null,
  };
}

// Team-mode game with more than two players (2v2, 1v3, 2v1v1) where every player
// has a team id. Older uploads were stored without team ids and use the normal layout.
export function isTeamGame(row, players) {
  return (
    Boolean(row?.is_teams) &&
    players.length > 2 &&
    players.every((player) => player.team_id !== null && player.team_id !== undefined)
  );
}

// Groups players by team id (0 red, 1 blue, 2 green), returning
// [{ teamId, players }] in the order of each team's lowest port.
export function groupPlayersByTeam(players) {
  const teams = new Map();
  players.forEach((player) => {
    if (!teams.has(player.team_id)) {
      teams.set(player.team_id, []);
    }
    teams.get(player.team_id).push(player);
  });
  return Array.from(teams, ([teamId, teamPlayers]) => ({ teamId, players: teamPlayers }));
}
