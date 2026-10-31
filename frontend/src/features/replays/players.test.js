import test from "node:test";
import assert from "node:assert/strict";

import { getPlayerDisplay, getPlayerDetails, getRowPlayers, groupPlayersByTeam, isTeamGame } from "./players.js";

test("getRowPlayers sorts by port and puts unknown ports last", () => {
  const row = { players: [{ port: 3, name: "c" }, { name: "x" }, { port: 1, name: "a" }, null] };
  assert.deepEqual(getRowPlayers(row).map((player) => player.name), ["a", "c", "x"]);
});

test("getRowPlayers falls back to legacy player_N_info fields", () => {
  const row = {
    player_1: "Alice",
    player_1_info: { port: 1 },
    player_2_info: { port: 2, name: "Bob" },
  };
  assert.deepEqual(getRowPlayers(row).map((player) => player.name), ["Alice", "Bob"]);
  assert.deepEqual(getRowPlayers(null), []);
});

test("getPlayerDisplay prefers display name, then name, code, tag", () => {
  assert.equal(getPlayerDisplay({ display_name: "D", name: "N", tag: "T" }).displayName, "D");
  assert.equal(getPlayerDisplay({ connect_code: "ABC#1", tag: "T" }).displayName, "ABC#1");
  assert.equal(getPlayerDisplay({ tag: "T" }).displayName, "T");
  assert.equal(getPlayerDisplay({}).displayName, "-");
});

test("getPlayerDisplay derives winner, cpu and rating defaults", () => {
  const display = getPlayerDisplay({ is_winner: 1, type: 1 });
  assert.equal(display.isWinner, true);
  assert.equal(display.isCpu, true);
  assert.equal(display.rating, "--");
  assert.equal(display.connectCode, "-");
  assert.equal(getPlayerDisplay({ rating: 0, is_winner: 0 }).rating, 0);
  assert.equal(getPlayerDisplay({ is_winner: 0 }).isWinner, false);
});

test("groupPlayersByTeam groups by team id in port order", () => {
  const players = [
    { port: 1, team_id: 1 },
    { port: 2, team_id: 0 },
    { port: 3, team_id: 1 },
    { port: 4, team_id: 2 },
  ];
  assert.deepEqual(
    groupPlayersByTeam(players).map(({ teamId, players: team }) => [teamId, team.map((player) => player.port)]),
    [[1, [1, 3]], [0, [2]], [2, [4]]],
  );
});

test("isTeamGame needs team mode, more than two players and team ids", () => {
  const four = [{ team_id: 0 }, { team_id: 1 }, { team_id: 0 }, { team_id: 1 }];
  assert.equal(isTeamGame({ is_teams: true }, four), true);
  assert.equal(isTeamGame({ is_teams: false }, four), false);
  assert.equal(isTeamGame({ is_teams: true }, four.slice(0, 2)), false);
  assert.equal(isTeamGame({ is_teams: true }, [...four.slice(0, 3), { team_id: null }]), false);
  assert.equal(isTeamGame({}, four), false);
});

test("getPlayerDetails collects what the tooltip shows", () => {
  const player = { display_name: "Mango", connect_code: "MANG#0", character_id: 2, port: 1, rank: "Master_II", rating: 2410 };
  assert.deepEqual(getPlayerDetails(player), {
    name: "Mango",
    isCpu: false,
    character: "Fox",
    connectCode: "MANG#0",
    port: 1,
    rankName: "Master II",
    rating: 2410,
  });
});

test("getPlayerDetails leaves missing values null and hides CPU codes", () => {
  assert.equal(getPlayerDetails({ type: 1 }).name, "CPU");
  assert.deepEqual(getPlayerDetails({ type: 1, display_name: "Bot", character_id: 22, port: 5, connect_code: "X#1" }), {
    name: "Bot",
    isCpu: true,
    character: "Dr. Mario",
    connectCode: null,
    port: null,
    rankName: null,
    rating: null,
  });
});
