import test from "node:test";
import assert from "node:assert/strict";

import { mergeReplayRows } from "./homeRowLifecycle.js";

function isoNowMinus(ms) {
  return new Date(Date.now() - ms).toISOString();
}

test("keeps connected live source as live row", () => {
  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-1",
          username: "streamer",
          connected: true,
          stream_phase: "started",
          player_preview: [{ name: "P1", port: 1 }],
          repositories: ["public"],
          connected_at: isoNowMinus(10_000),
          updated_at: isoNowMinus(2_000),
          last_activity_at: isoNowMinus(2_000),
          stream_game_id: "g-1",
        },
      ],
      events: [],
    },
    files: [],
    nowMs: Date.now(),
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].lifecycle, "live");
  assert.equal(rows[0].source_label, "Live stream");
});

test("hides connected source until slp preview metadata exists", () => {
  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-0",
          username: "streamer",
          connected: true,
          stream_phase: "started",
          player_preview: [],
          repositories: ["public"],
          connected_at: isoNowMinus(10_000),
          updated_at: isoNowMinus(2_000),
          last_activity_at: isoNowMinus(2_000),
          stream_game_id: "g-0",
        },
      ],
      events: [],
    },
    files: [],
    nowMs: Date.now(),
  });

  assert.equal(rows.length, 0);
});

test("marks disconnected non-terminal source as finalizing", () => {
  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-1",
          username: "streamer",
          connected: false,
          stream_phase: "pending_parse",
          player_preview: [{ name: "P1", port: 1 }],
          repositories: ["public"],
          connected_at: isoNowMinus(20_000),
          updated_at: isoNowMinus(1_000),
          last_activity_at: isoNowMinus(1_000),
          stream_game_id: "g-2",
        },
      ],
      events: [],
    },
    files: [],
    nowMs: Date.now(),
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].lifecycle, "finalizing");
  assert.equal(rows[0].source_label, "Finalizing upload");
});

test("hides live row when terminal event arrives even without completed row", () => {
  const now = Date.now();
  const connectedAt = new Date(now - 30_000).toISOString();

  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-2",
          username: "streamer",
          connected: false,
          stream_phase: "pending_parse",
          player_preview: [{ name: "P1", port: 1 }],
          repositories: ["public"],
          connected_at: connectedAt,
          updated_at: new Date(now - 1_000).toISOString(),
          last_activity_at: new Date(now - 1_000).toISOString(),
          stream_game_id: "g-3",
        },
      ],
      events: [
        {
          source_name: "setup-2",
          status: "ended",
          timestamp: new Date(now - 500).toISOString(),
          stream_game_id: "g-3",
        },
      ],
    },
    files: [],
    nowMs: now,
  });

  assert.equal(rows.length, 0);
});

test("replaces live row when completed row with same stream_game_id exists", () => {
  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-3",
          username: "streamer",
          connected: true,
          stream_phase: "started",
          player_preview: [{ name: "P1", port: 1 }],
          repositories: ["public"],
          connected_at: isoNowMinus(20_000),
          updated_at: isoNowMinus(2_000),
          last_activity_at: isoNowMinus(2_000),
          stream_game_id: "g-4",
        },
      ],
      events: [],
    },
    files: [
      {
        id: 123,
        folder: "uploads/public/setup-3/2026/07/23",
        name: "game.slp",
        stream_game_id: "g-4",
        birth_time: new Date().toISOString(),
      },
    ],
    nowMs: Date.now(),
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].lifecycle, "completed");
  assert.equal(rows[0].id, 123);
});

test("can defer live rows until completed rows are ready", () => {
  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-4",
          username: "streamer",
          connected: true,
          stream_phase: "started",
          player_preview: [{ name: "P1", port: 1 }],
          repositories: ["public"],
          connected_at: isoNowMinus(20_000),
          updated_at: isoNowMinus(2_000),
          last_activity_at: isoNowMinus(2_000),
          stream_game_id: "g-5",
        },
      ],
      events: [],
    },
    files: [
      {
        id: 456,
        folder: "uploads/public/setup-4/2026/07/24",
        name: "completed.slp",
        birth_time: new Date().toISOString(),
      },
    ],
    nowMs: Date.now(),
    includeLiveRows: false,
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].lifecycle, "completed");
  assert.equal(rows[0].id, 456);
});
