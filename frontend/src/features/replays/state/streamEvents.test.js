import test from "node:test";
import assert from "node:assert/strict";

import { getTerminalRowKey, shouldAdvanceMirror } from "./streamEvents.js";

test("getTerminalRowKey keys ended streams by game id, then source", () => {
  assert.equal(getTerminalRowKey({ status: "ended", stream_game_id: " g-1 ", source_name: "wii-1" }), "stream:g-1");
  assert.equal(getTerminalRowKey({ status: "ABANDONED", source_name: "wii-1" }), "source:wii-1");
  assert.equal(getTerminalRowKey({ status: "failed" }), "");
});

test("getTerminalRowKey ignores non-terminal statuses", () => {
  assert.equal(getTerminalRowKey({ status: "started", stream_game_id: "g-1" }), "");
  assert.equal(getTerminalRowKey({ status: "pending_parse", stream_game_id: "g-1" }), "");
  assert.equal(getTerminalRowKey(null), "");
});

test("shouldAdvanceMirror fires only for a newer game on the followed source", () => {
  const follow = { followSource: "wii-1", lastMirroredGameId: "g-1" };
  assert.equal(shouldAdvanceMirror({ status: "started", source_name: "wii-1", stream_game_id: "g-2" }, follow), true);
  assert.equal(shouldAdvanceMirror({ status: "started", source_name: "wii-1", stream_game_id: "g-1" }, follow), false);
  assert.equal(shouldAdvanceMirror({ status: "started", source_name: "wii-2", stream_game_id: "g-2" }, follow), false);
  assert.equal(shouldAdvanceMirror({ status: "ended", source_name: "wii-1", stream_game_id: "g-2" }, follow), false);
  assert.equal(shouldAdvanceMirror({ status: "started", source_name: "wii-1" }, follow), false);
  assert.equal(
    shouldAdvanceMirror({ status: "started", source_name: "wii-1", stream_game_id: "g-2" }, { followSource: "", lastMirroredGameId: "" }),
    false,
  );
});
