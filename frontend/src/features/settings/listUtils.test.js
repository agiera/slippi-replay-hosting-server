import test from "node:test";
import assert from "node:assert/strict";

import { defaultTokenRepositoryId, replaceById, sortByName, toggleId } from "./listUtils.js";

test("sortByName sorts a copy alphabetically", () => {
  const items = [{ name: "locals" }, { name: "genesis" }];
  assert.deepEqual(sortByName(items).map((item) => item.name), ["genesis", "locals"]);
  assert.equal(items[0].name, "locals");
});

test("replaceById swaps only the matching item", () => {
  const items = [{ id: 1, v: "a" }, { id: 2, v: "b" }];
  assert.deepEqual(replaceById(items, { id: 2, v: "c" }), [{ id: 1, v: "a" }, { id: 2, v: "c" }]);
});

test("toggleId adds and removes ids", () => {
  assert.deepEqual(toggleId([1, 2], 3), [1, 2, 3]);
  assert.deepEqual(toggleId([1, 2, 3], 2), [1, 3]);
});

test("defaultTokenRepositoryId prefers the viewer's own repository", () => {
  const all = [{ id: 5 }, { id: 6 }];
  assert.equal(defaultTokenRepositoryId({ repositories: [{ id: 6 }] }, all), "6");
  assert.equal(defaultTokenRepositoryId({ repositories: [] }, all), "5");
  assert.equal(defaultTokenRepositoryId(null, []), "");
});
