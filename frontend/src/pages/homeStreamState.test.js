import test from "node:test";
import assert from "node:assert/strict";

import {
  applySnapshotOrStatusFrame,
  applyStreamEventFrame,
  newestRefreshEventMs,
  shouldRefreshReplayList,
} from "./homeStreamState.js";

test("newestRefreshEventMs picks newest qualifying status timestamp", () => {
  const events = [
    { status: "started", timestamp: "2026-01-01T00:00:01Z" },
    { status: "pending_parse", timestamp: "2026-01-01T00:00:03Z" },
    { status: "completed", timestamp: "2026-01-01T00:00:02Z" },
  ];

  const ms = newestRefreshEventMs(events);
  assert.equal(ms, new Date("2026-01-01T00:00:03Z").getTime());
});

test("shouldRefreshReplayList compares latest event against watermark", () => {
  const events = [{ status: "ended", timestamp: "2026-01-01T00:00:04Z" }];
  const oldMark = new Date("2026-01-01T00:00:03Z").getTime();

  const decision = shouldRefreshReplayList(events, oldMark);
  assert.equal(decision.shouldRefresh, true);
  assert.equal(decision.newestMs, new Date("2026-01-01T00:00:04Z").getTime());
});

test("applySnapshotOrStatusFrame keeps prior events when payload events missing", () => {
  const prev = {
    tournament: null,
    sources: [],
    events: [{ event_id: 7, status: "started" }],
  };

  const next = applySnapshotOrStatusFrame(prev, { tournament: { id: 1 }, sources: [] });

  assert.equal(next.tournament.id, 1);
  assert.equal(next.events.length, 1);
  assert.equal(next.events[0].event_id, 7);
});

test("applySnapshotOrStatusFrame preserves rank enrichment across sparse status frames", () => {
  const prev = {
    tournament: null,
    sources: [
      {
        source_name: "setup-rank",
        stream_game_id: "g-rank",
        rank_lookup_complete: true,
        player_preview: [
          {
            port: 1,
            connect_code: "MANGO#0",
            rank: "Master_I",
            rating: 2200,
          },
        ],
      },
    ],
    events: [],
  };

  const payload = {
    tournament: null,
    sources: [
      {
        source_name: "setup-rank",
        stream_game_id: "g-rank",
        player_preview: [
          {
            port: 1,
            connect_code: "MANGO#0",
            rank: null,
            rating: null,
          },
        ],
      },
    ],
  };

  const next = applySnapshotOrStatusFrame(prev, payload);
  assert.equal(next.sources.length, 1);
  assert.equal(next.sources[0].rank_lookup_complete, true);
  assert.equal(next.sources[0].player_preview[0].rank, "Master_I");
  assert.equal(next.sources[0].player_preview[0].rating, 2200);
});

test("applyStreamEventFrame prepends and dedupes by event_id", () => {
  const prev = {
    tournament: null,
    sources: [],
    events: [{ event_id: 10, status: "started" }, { event_id: 9, status: "started" }],
  };

  const incomingDuplicate = { event_id: 10, status: "completed" };
  const next = applyStreamEventFrame(prev, incomingDuplicate);

  assert.equal(next.events.length, 2);
  assert.equal(next.events[0].event_id, 10);
  assert.equal(next.events[0].status, "completed");
  assert.equal(next.events[1].event_id, 9);
});
