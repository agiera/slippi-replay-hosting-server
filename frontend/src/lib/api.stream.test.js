import test from "node:test";
import assert from "node:assert/strict";

import { normalizeStreamEventPayload, normalizeStreamStatusPayload } from "./api.js";

test("normalizeStreamEventPayload maps slippi_code to connect_code and name fallback", () => {
  const normalized = normalizeStreamEventPayload({
    slippi_code: "ABCD#123",
    character_id: 2,
    port: 1,
  });

  assert.equal(normalized.connect_code, "ABCD#123");
  assert.equal(normalized.name, "ABCD#123");
  assert.equal(normalized.character_id, 2);
  assert.equal(normalized.port, 1);
  assert.equal(normalized.is_cpu, false);
});

test("normalizeStreamStatusPayload normalizes source player previews", () => {
  const payload = {
    tournament: { id: 1, name: "Test Open" },
    sources: [
      {
        source_name: "setup-1",
        player_preview: [
          {
            display_name: "Mango",
            connect_code: "MANGO#0",
            rank: "Master_I",
          },
        ],
      },
    ],
    events: [{ event_id: 1, status: "started" }],
  };

  const normalized = normalizeStreamStatusPayload(payload, []);

  assert.equal(normalized.tournament.name, "Test Open");
  assert.equal(normalized.sources.length, 1);
  assert.equal(normalized.sources[0].player_preview.length, 1);
  assert.equal(normalized.sources[0].player_preview[0].name, "Mango");
  assert.equal(normalized.sources[0].player_preview[0].connect_code, "MANGO#0");
  assert.deepEqual(normalized.events, payload.events);
});

test("normalizeStreamStatusPayload maps sidecar-style preview fields for the UI", () => {
  const payload = {
    sources: [
      {
        source_name: "setup-1",
        player_preview: [
          {
            display_name: "Test User1",
            slippi_code: "TEST#001",
            firmware: "1.0.0",
            port: 1,
          },
          {
            display_name: "Test User2",
            slippi_code: "TEST#002",
            firmware: "1.0.0",
            port: 2,
          },
        ],
      },
    ],
  };

  const normalized = normalizeStreamStatusPayload(payload, []);

  assert.equal(normalized.sources[0].player_preview[0].name, "Test User1");
  assert.equal(normalized.sources[0].player_preview[0].connect_code, "TEST#001");
  assert.equal(normalized.sources[0].player_preview[0].firmware, "1.0.0");
  assert.equal(normalized.sources[0].player_preview[1].name, "Test User2");
  assert.equal(normalized.sources[0].player_preview[1].connect_code, "TEST#002");
});

test("normalizeStreamStatusPayload uses fallback events when events are missing", () => {
  const fallbackEvents = [{ event_id: 99, status: "heartbeat" }];
  const normalized = normalizeStreamStatusPayload({ sources: [] }, fallbackEvents);

  assert.deepEqual(normalized.events, fallbackEvents);
});
