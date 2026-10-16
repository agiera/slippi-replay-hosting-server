import test from "node:test";
import assert from "node:assert/strict";

import {
  buildApiUrl,
  buildSlippiDeepLink,
  buildSlippiLabViewerUrl,
  buildSlippiProfileUrl,
  buildSlippiMirrorDeepLink,
  resolveReplayDownloadUrl,
} from "./links.js";

const options = { base: "/api/v1", origin: "https://replays.example" };

test("buildApiUrl resolves a relative base against the origin", () => {
  assert.equal(buildApiUrl("/replays/files", options), "https://replays.example/api/v1/replays/files");
});

test("buildApiUrl keeps an absolute base and strips trailing slashes", () => {
  assert.equal(
    buildApiUrl("/replays/files", { base: "https://api.example/v1//" }),
    "https://api.example/v1/replays/files",
  );
});

test("resolveReplayDownloadUrl prefers download_url over the file id", () => {
  assert.equal(
    resolveReplayDownloadUrl({ download_url: "/replays/files/7/download?sig=x", fileId: 3 }, options),
    "https://replays.example/api/v1/replays/files/7/download?sig=x",
  );
  assert.equal(
    resolveReplayDownloadUrl({ id: 3 }, options),
    "https://replays.example/api/v1/replays/files/3/download",
  );
  assert.equal(resolveReplayDownloadUrl({}, options), "");
});

test("buildSlippiDeepLink encodes the replay url", () => {
  assert.equal(
    buildSlippiDeepLink("https://replays.example/a b.slp"),
    "slippi://play?path=https%3A%2F%2Freplays.example%2Fa%20b.slp",
  );
  assert.equal(buildSlippiDeepLink(""), "");
});

test("buildSlippiMirrorDeepLink targets the live source download and console", () => {
  const link = buildSlippiMirrorDeepLink(" Wii 1 ", options);
  const liveUrl = "https://replays.example/api/v1/replays/stream/sources/Wii%201/download";
  assert.equal(link, `slippi://play?path=${encodeURIComponent(liveUrl)}&mirror=1&console=Wii%201`);
  assert.equal(buildSlippiMirrorDeepLink("  ", options), "");
});

test("buildSlippiLabViewerUrl needs both a replay url and a SlippiLab url", () => {
  assert.equal(
    buildSlippiLabViewerUrl("https://replays.example/x.slp", "https://lab.example"),
    "https://lab.example?replayUrl=https%3A%2F%2Freplays.example%2Fx.slp",
  );
  assert.equal(buildSlippiLabViewerUrl("https://replays.example/x.slp", ""), "");
  assert.equal(buildSlippiLabViewerUrl("", "https://lab.example"), "");
});

test("buildSlippiProfileUrl turns a connect code into a slippi.gg profile link", () => {
  assert.equal(buildSlippiProfileUrl("ant#0"), "https://slippi.gg/user/ant-0");
  assert.equal(buildSlippiProfileUrl("MANG#0"), "https://slippi.gg/user/mang-0");
  assert.equal(buildSlippiProfileUrl(" ZAIN#123 "), "https://slippi.gg/user/zain-123");
});

test("buildSlippiProfileUrl is empty without a valid code", () => {
  assert.equal(buildSlippiProfileUrl(null), "");
  assert.equal(buildSlippiProfileUrl(""), "");
  assert.equal(buildSlippiProfileUrl("-"), "");
  assert.equal(buildSlippiProfileUrl("ANT"), "");
});
