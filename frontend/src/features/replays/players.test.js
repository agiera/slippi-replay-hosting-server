import test from "node:test";
import assert from "node:assert/strict";

import { getPlayerDisplay, getRowPlayers } from "./players.js";

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
