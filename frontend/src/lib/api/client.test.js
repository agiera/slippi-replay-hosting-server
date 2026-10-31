import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";

import { installBrowserGlobals, stubFetch } from "./testGlobals.js";
import { ApiError, buildQuery, isAccessTokenExpired, request } from "./client.js";
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

function jwtWithExp(expSeconds) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256" })}.${encode({ sub: "1", exp: expSeconds })}.sig`;
}

test("isAccessTokenExpired reads the JWT exp and ignores opaque tokens", () => {
  const nowMs = 1_000_000_000_000;
  assert.equal(isAccessTokenExpired(jwtWithExp(nowMs / 1000 - 1), nowMs), true);
  assert.equal(isAccessTokenExpired(jwtWithExp(nowMs / 1000 + 10), nowMs), true);
  assert.equal(isAccessTokenExpired(jwtWithExp(nowMs / 1000 + 3600), nowMs), false);
  assert.equal(isAccessTokenExpired("opaque", nowMs), false);
  assert.equal(isAccessTokenExpired(null, nowMs), false);
});

test("request refreshes an expired access token before sending it", async () => {
  storage.setItem("token", jwtWithExp(Date.now() / 1000 - 60));
  storage.setItem("refresh_token", "refresh-1");
  const calls = stubFetch([
    { body: { access_token: "fresh", refresh_token: "refresh-2", user: { id: 1 } } },
    { body: { items: [] } },
  ]);

  await request("/replays/files");

  assert.equal(calls[0].url, "/api/v1/auth/refresh");
  assert.equal(calls[1].headers.Authorization, `Bearer fresh`);
  assert.equal(storage.getItem("refresh_token"), "refresh-2");
});

test("concurrent requests share one refresh", async () => {
  storage.setItem("token", jwtWithExp(Date.now() / 1000 - 60));
  storage.setItem("refresh_token", "refresh-1");
  const calls = stubFetch([
    { body: { access_token: "fresh", refresh_token: "refresh-2", user: { id: 1 } } },
    { body: {} },
    { body: {} },
  ]);

  await Promise.all([request("/a"), request("/b")]);

  assert.equal(calls.filter((call) => call.url.endsWith("/auth/refresh")).length, 1);
  assert.ok(calls.slice(1).every((call) => call.headers.Authorization === `Bearer fresh`));
});

test("request goes anonymous when the refresh token is rejected", async () => {
  storage.setItem("token", jwtWithExp(Date.now() / 1000 - 60));
  storage.setItem("refresh_token", "revoked");
  const calls = stubFetch([{ status: 401, body: { detail: "invalid" } }, { body: {} }]);

  await request("/replays/files");

  assert.deepEqual(calls[1].headers, {});
  assert.equal(storage.getItem("token"), null);
});
