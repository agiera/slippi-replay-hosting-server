import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";

import { installBrowserGlobals, stubFetch } from "./testGlobals.js";
import { ApiError, buildQuery, request } from "./client.js";
import { fetchReplayFiles } from "./replays.js";

let storage;

beforeEach(() => {
  storage = installBrowserGlobals();
});

test("buildQuery skips empty values but keeps zero and false", () => {
  assert.equal(buildQuery({ a: "x", b: "", c: null, d: undefined, e: 0, f: false }), "?a=x&e=0&f=false");
  assert.equal(buildQuery({}), "");
});

test("request sends the bearer token and a JSON body", async () => {
  storage.setItem("token", "abc");
  const calls = stubFetch([{ body: { ok: true } }]);

  const result = await request("/things", { method: "POST", body: { name: "n" }, query: { q: "1" } });

  assert.deepEqual(result, { ok: true });
  assert.equal(calls[0].url, "/api/v1/things?q=1");
  assert.equal(calls[0].method, "POST");
  assert.equal(calls[0].body, JSON.stringify({ name: "n" }));
  assert.deepEqual(calls[0].headers, { Authorization: "Bearer abc", "Content-Type": "application/json" });
});

test("request omits auth when there is no token or auth is false", async () => {
  const calls = stubFetch([{ body: {} }, { body: {} }]);
  await request("/a");
  storage.setItem("token", "abc");
  await request("/b", { auth: false });
  assert.deepEqual(calls[0].headers, {});
  assert.deepEqual(calls[1].headers, {});
});

test("request throws ApiError with the server detail and status", async () => {
  stubFetch([{ status: 403, body: { detail: "Forbidden" } }]);
  await assert.rejects(request("/x"), (err) => err instanceof ApiError && err.status === 403 && err.message === "Forbidden");
});

test("request joins FastAPI validation errors and falls back on unreadable bodies", async () => {
  stubFetch([
    { status: 422, body: { detail: [{ msg: "field required" }, { msg: "too short" }] } },
    { status: 500 },
  ]);
  await assert.rejects(request("/x"), { message: "field required; too short" });
  await assert.rejects(request("/x"), { message: "Request failed", status: 500 });
});

test("request returns null for 204 responses", async () => {
  stubFetch([{ status: 204 }]);
  assert.equal(await request("/x", { method: "DELETE" }), null);
});

test("fetchReplayFiles only forwards known filter keys", async () => {
  const calls = stubFetch([{ body: { items: [], next_cursor: null } }]);
  await fetchReplayFiles({ keyword: "fox", limit: 40, cursor: null, ranked: "", bogus: "1" });
  assert.equal(calls[0].url, "/api/v1/replays/files?limit=40&keyword=fox");
});
