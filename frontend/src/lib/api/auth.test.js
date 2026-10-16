import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";

import { installBrowserGlobals, stubFetch } from "./testGlobals.js";
import { fetchMe, logout, refreshSession } from "./auth.js";

let storage;

beforeEach(() => {
  storage = installBrowserGlobals();
  storage.setItem("token", "old-access");
  storage.setItem("refresh_token", "refresh-1");
});

test("fetchMe refreshes once on 401 and retries with the new token", async () => {
  const calls = stubFetch([
    { status: 401, body: { detail: "expired" } },
    { body: { access_token: "new-access", refresh_token: "refresh-2", user: { id: 1 } } },
    { body: { id: 1, username: "ant" } },
  ]);

  const user = await fetchMe();

  assert.deepEqual(user, { id: 1, username: "ant" });
  assert.equal(calls[1].url, "/api/v1/auth/refresh");
  assert.equal(calls[2].headers.Authorization, "Bearer new-access");
  assert.equal(storage.getItem("refresh_token"), "refresh-2");
  assert.equal(storage.getItem("user"), JSON.stringify(user));
});

test("fetchMe surfaces non-401 errors without refreshing", async () => {
  const calls = stubFetch([{ status: 500, body: { detail: "boom" } }]);
  await assert.rejects(fetchMe(), { message: "boom" });
  assert.equal(calls.length, 1);
});

test("refreshSession clears the session when the server rejects the token", async () => {
  stubFetch([{ status: 401, body: { detail: "invalid" } }]);
  await assert.rejects(refreshSession(), { message: "invalid" });
  assert.equal(storage.getItem("token"), null);
  assert.equal(storage.getItem("refresh_token"), null);
});

test("refreshSession keeps the session on a network failure", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  await assert.rejects(refreshSession(), TypeError);
  assert.equal(storage.getItem("refresh_token"), "refresh-1");
});

test("logout clears the local session even if the server call fails", async () => {
  stubFetch([{ status: 500 }]);
  await logout();
  assert.equal(storage.getItem("token"), null);
  assert.equal(storage.getItem("refresh_token"), null);
});
