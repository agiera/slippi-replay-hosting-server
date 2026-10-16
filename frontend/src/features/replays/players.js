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
