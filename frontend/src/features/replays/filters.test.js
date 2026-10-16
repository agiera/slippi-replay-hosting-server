import test from "node:test";
import assert from "node:assert/strict";

import {
  INITIAL_FILTERS,
  buildSearchParams,
  describeActiveFilters,
  parseCostumeSelection,
  parseFiltersFromSearch,
  parseSelectedCharacterIds,
  pruneCostumeSelection,
  serializeCostumeSelection,
} from "./filters.js";

test("parseFiltersFromSearch fills every filter key and keeps INITIAL_FILTERS order", () => {
  const filters = parseFiltersFromSearch(new URLSearchParams("keyword=fox&rank=Gold_I"));
  assert.deepEqual(Object.keys(filters), Object.keys(INITIAL_FILTERS));
  assert.equal(filters.keyword, "fox");
  assert.equal(filters.rank, "Gold_I");
  assert.equal(filters.player, "");
});

test("parseFiltersFromSearch reads legacy collection as source", () => {
  assert.equal(parseFiltersFromSearch(new URLSearchParams("collection=wii1")).source, "wii1");
  assert.equal(parseFiltersFromSearch(new URLSearchParams("source=wii2&collection=wii1")).source, "wii2");
});

test("buildSearchParams round-trips and omits empty values", () => {
  const filters = { ...INITIAL_FILTERS, character: "2,9", date_from: "2025-01-01" };
  const params = buildSearchParams(filters);
  assert.equal(params.toString(), "character=2%2C9&date_from=2025-01-01");
  assert.deepEqual(parseFiltersFromSearch(params), filters);
});

test("parseSelectedCharacterIds drops junk and unknown ids", () => {
  assert.deepEqual(parseSelectedCharacterIds("2, 9,abc,,99,-1"), [2, 9]);
  assert.deepEqual(parseSelectedCharacterIds(""), []);
});

test("costume selection parses and serializes sorted pairs", () => {
  const selection = parseCostumeSelection("9:1,2:3,2:0,bad,2:x");
  assert.deepEqual([...selection.keys()], [9, 2]);
  assert.deepEqual([...selection.get(2)], [3, 0]);
  assert.equal(serializeCostumeSelection(selection), "2:0,2:3,9:1");
});

test("pruneCostumeSelection drops unselected characters and missing costumes", () => {
  const costumes = { 2: [0, 1, 2, 3], 9: [0, 1] };
  const getCostumeIds = (characterId) => costumes[characterId] || [0];

  assert.equal(pruneCostumeSelection("2:1,2:7,9:1", [2], getCostumeIds), "2:1");
  assert.equal(pruneCostumeSelection("2:1,9:1", [2, 9], getCostumeIds), "2:1,9:1");
  assert.equal(pruneCostumeSelection("2:1", [], getCostumeIds), "");
});

test("describeActiveFilters labels each set filter in a stable order", () => {
  const filters = {
    ...INITIAL_FILTERS,
    keyword: "grand finals",
    character: "2,9",
    costume: "2:0,2:3",
    rank: "Gold_I,Diamond_II",
    min_rank: "1400",
    repository: "genesis,locals,scratch",
    include_handwarmers: "1",
    date_from: "2026-10-01",
  };

  assert.deepEqual(describeActiveFilters(filters), [
    { key: "keyword", label: "“grand finals”" },
    { key: "character", label: "Fox, Marth" },
    { key: "costume", label: "2 costumes" },
    { key: "rank", label: "Rank: Gold I to Diamond II" },
    { key: "min_rank", label: "Rating 1400+" },
    { key: "repository", label: "Repository: 3 selected" },
    { key: "include_handwarmers", label: "With hand warmers" },
    { key: "date_from", label: "From Oct 1, 2026" },
  ]);
});

test("describeActiveFilters skips empty and unrecognised selections", () => {
  assert.deepEqual(describeActiveFilters(INITIAL_FILTERS), []);
  assert.deepEqual(describeActiveFilters({ ...INITIAL_FILTERS, character: "999" }), []);
});
