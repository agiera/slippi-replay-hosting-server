import test from "node:test";
import assert from "node:assert/strict";

import { formatGameDuration, formatPlayedDateTime, formatRelativeTime, formatStageName } from "./format.js";

test("formatGameDuration renders minutes and seconds", () => {
  assert.equal(formatGameDuration(90), "1m 30s");
  assert.equal(formatGameDuration(185), "3m 5s");
  assert.equal(formatGameDuration(0), "0m 0s");
  assert.equal(formatGameDuration(-4), "0m 0s");
});

test("formatGameDuration shows a dash when missing", () => {
  assert.equal(formatGameDuration(null), "-");
  assert.equal(formatGameDuration(undefined), "-");
});

test("formatPlayedDateTime renders local 12-hour time", () => {
  const evening = new Date(2025, 2, 4, 19, 5).toISOString();
  assert.equal(formatPlayedDateTime(evening), "Mar 4, 2025 - 7:05pm");

  const midnight = new Date(2025, 0, 1, 0, 30).toISOString();
  assert.equal(formatPlayedDateTime(midnight), "Jan 1, 2025 - 12:30am");
});

test("formatPlayedDateTime passes through unparseable values", () => {
  assert.equal(formatPlayedDateTime(""), "-");
  assert.equal(formatPlayedDateTime("not a date"), "not a date");
});

test("formatStageName maps known ids and falls back for unknown ones", () => {
  assert.equal(formatStageName(31), "Battlefield");
  assert.equal(formatStageName("32"), "Final Destination");
  assert.equal(formatStageName(99), "Stage 99");
  assert.equal(formatStageName(null), "-");
});

test("formatRelativeTime counts up from now, then falls back to a date", () => {
  const now = new Date(2026, 9, 16, 12, 0).getTime();
  const ago = (ms) => new Date(now - ms).toISOString();

  assert.equal(formatRelativeTime(ago(20_000), now), "Just now");
  assert.equal(formatRelativeTime(ago(-5_000), now), "Just now");
  assert.equal(formatRelativeTime(ago(12 * 60_000), now), "12 min ago");
  assert.equal(formatRelativeTime(ago(3 * 3_600_000), now), "3 hr ago");
  assert.equal(formatRelativeTime(ago(30 * 3_600_000), now), "Yesterday");
  assert.equal(formatRelativeTime(ago(4 * 86_400_000), now), "4 days ago");
  assert.equal(formatRelativeTime(new Date(2026, 2, 4, 9).toISOString(), now), "Mar 4");
  assert.equal(formatRelativeTime(new Date(2024, 2, 4, 9).toISOString(), now), "Mar 4, 2024");
});

test("formatRelativeTime passes through missing and unparseable values", () => {
  assert.equal(formatRelativeTime("", 0), "-");
  assert.equal(formatRelativeTime("not a date", 0), "not a date");
});
