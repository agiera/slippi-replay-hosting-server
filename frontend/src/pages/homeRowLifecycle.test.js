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
  assert.equal(rows[0].source_label, "setup-1");
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

test("keeps connected source visible beyond stale timeout window", () => {
  const now = Date.now();
  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-long",
          username: "streamer",
          connected: true,
          stream_phase: "started",
          player_preview: [{ name: "P1", port: 1, connect_code: "P1#111", rank: "Gold_I", rating: 1600 }],
          repositories: ["public"],
          connected_at: new Date(now - 5 * 60_000).toISOString(),
          updated_at: new Date(now - 5 * 60_000).toISOString(),
          last_activity_at: new Date(now - 5 * 60_000).toISOString(),
          stream_game_id: "g-long",
          rank_lookup_complete: true,
        },
      ],
      events: [],
    },
    files: [],
    nowMs: now,
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].lifecycle, "live");
});

test("shows connected source while rank enrichment is pending", () => {
  const now = Date.now();
  const baseSource = {
    source_name: "setup-rank",
    username: "streamer",
    connected: true,
    stream_phase: "started",
    repositories: ["public"],
    connected_at: new Date(now - 10_000).toISOString(),
    updated_at: new Date(now - 2_000).toISOString(),
    last_activity_at: new Date(now - 2_000).toISOString(),
    stream_game_id: "g-rank",
    player_preview: [{ name: "P1", connect_code: "MANGO#0", port: 1 }],
  };

  const hiddenRows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [{ ...baseSource, rank_lookup_complete: false }],
      events: [],
    },
    files: [],
    nowMs: now,
  });

  assert.equal(hiddenRows.length, 1);
  assert.equal(hiddenRows[0].lifecycle, "live");

  const visibleRows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [{ ...baseSource, rank_lookup_complete: true, player_preview: [{ name: "P1", connect_code: "MANGO#0", port: 1, rank: "Master_I", rating: 2200 }] }],
      events: [],
    },
    files: [],
    nowMs: now,
  });

  assert.equal(visibleRows.length, 1);
  assert.equal(visibleRows[0].lifecycle, "live");
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
  assert.equal(rows[0].source_label, "setup-1");
});

test("marks connected terminal source as finalizing", () => {
  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-1",
          username: "streamer",
          connected: true,
          stream_phase: "ended",
          player_preview: [{ name: "P1", port: 1 }],
          repositories: ["public"],
          connected_at: isoNowMinus(20_000),
          updated_at: isoNowMinus(1_000),
          last_activity_at: isoNowMinus(1_000),
          stream_game_id: "g-2",
        },
      ],
      events: [
        {
          source_name: "setup-1",
          status: "ended",
          timestamp: isoNowMinus(900),
          stream_game_id: "g-2",
        },
      ],
    },
    files: [],
    nowMs: Date.now(),
    preservedTerminalRows: ["stream:g-2"],
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].lifecycle, "finalizing");
});

test("marks connected pending-parse source as finalizing", () => {
  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-pending",
          username: "streamer",
          connected: true,
          stream_phase: "pending_parse",
          player_preview: [{ name: "P1", port: 1 }],
          repositories: ["public"],
          connected_at: isoNowMinus(20_000),
          updated_at: isoNowMinus(1_000),
          last_activity_at: isoNowMinus(1_000),
          stream_game_id: "g-pending",
        },
      ],
      events: [],
    },
    files: [],
    nowMs: Date.now(),
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].lifecycle, "finalizing");
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

test("keeps terminal row visible during replacement refresh window", () => {
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
          stream_phase: "ended",
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
    preservedTerminalRows: ["stream:g-3"],
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].lifecycle, "finalizing");
});

test("shows preserved terminal row as finalizing even when stream_phase is stale started", () => {
  const now = Date.now();
  const connectedAt = new Date(now - 30_000).toISOString();

  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-2",
          username: "streamer",
          connected: true,
          stream_phase: "started",
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
    preservedTerminalRows: ["stream:g-3"],
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].lifecycle, "finalizing");
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
  assert.equal(rows[0].rowKey, "stream:g-4");
});

test("replaces completed row in the live row position for smooth transition", () => {
  const rows = mergeReplayRows({
    streamStatus: {
      tournament: null,
      sources: [
        {
          source_name: "setup-a",
          username: "streamer",
          connected: true,
          stream_phase: "started",
          player_preview: [{ name: "P1", port: 1 }],
          repositories: ["public"],
          connected_at: isoNowMinus(20_000),
          updated_at: isoNowMinus(2_000),
          last_activity_at: isoNowMinus(2_000),
          stream_game_id: "g-a",
        },
        {
          source_name: "setup-b",
          username: "streamer",
          connected: true,
          stream_phase: "started",
          player_preview: [{ name: "P2", port: 1 }],
          repositories: ["public"],
          connected_at: isoNowMinus(20_000),
          updated_at: isoNowMinus(2_000),
          last_activity_at: isoNowMinus(2_000),
          stream_game_id: "g-b",
        },
      ],
      events: [],
    },
    files: [
      {
        id: 321,
        folder: "uploads/public/setup-a/2026/07/24",
        name: "game-a.slp",
        stream_game_id: "g-a",
        birth_time: new Date().toISOString(),
      },
    ],
    nowMs: Date.now(),
  });

  assert.equal(rows.length, 2);
  assert.equal(rows[0].lifecycle, "completed");
  assert.equal(rows[0].id, 321);
  assert.equal(rows[0].rowKey, "stream:g-a");
  assert.equal(rows[1].lifecycle, "live");
  assert.equal(rows[1].stream_game_id, "g-b");
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
