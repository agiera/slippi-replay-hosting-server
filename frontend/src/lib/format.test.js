import test from "node:test";
import assert from "node:assert/strict";

import { formatGameDuration, formatPlayedDateTime, formatStageName } from "./format.js";

test("formatGameDuration renders minutes and seconds", () => {
  assert.equal(formatGameDuration(185), "3m5s");
  assert.equal(formatGameDuration(0), "0m0s");
  assert.equal(formatGameDuration(-4), "0m0s");
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
