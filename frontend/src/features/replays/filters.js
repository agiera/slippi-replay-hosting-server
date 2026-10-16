// Replay filter state <-> URL search params, plus the character/costume
// selection encoding ("2,9" for characters, "2:0,2:3" for character:costume).
import { CHARACTER_BY_ID } from "../../data/characters.js";

export const INITIAL_FILTERS = {
  keyword: "",
  character: "",
  costume: "",
  ranked: "",
  rank: "",
  min_rank: "",
  max_rank: "",
  player: "",
  repository: "",
  tournament: "",
  source: "",
  include_handwarmers: "",
  date_from: "",
  date_to: "",
};

export function parseFiltersFromSearch(searchParams) {
  const filters = {};
  Object.keys(INITIAL_FILTERS).forEach((key) => {
    filters[key] = searchParams.get(key) || "";
  });
  // `collection` is the legacy name for `source`.
  filters.source = filters.source || searchParams.get("collection") || "";
  return filters;
}

export function buildSearchParams(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  return params;
}

export function parseSelectedCharacterIds(value) {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => Number(part))
    .filter((id) => Number.isInteger(id) && CHARACTER_BY_ID.has(id));
}

// "2:0,2:3,9:1" -> Map { 2 => Set {0, 3}, 9 => Set {1} }
export function parseCostumeSelection(value) {
  const selections = new Map();
  if (!value) {
    return selections;
  }

  value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .forEach((pair) => {
      const [characterRaw, costumeRaw] = pair.split(":");
      const characterId = Number(characterRaw);
      const costumeId = Number(costumeRaw);
      if (!Number.isInteger(characterId) || !Number.isInteger(costumeId)) {
        return;
      }
      if (!selections.has(characterId)) {
        selections.set(characterId, new Set());
      }
      selections.get(characterId).add(costumeId);
    });

  return selections;
}

export function serializeCostumeSelection(selections) {
  const pairs = [];
  Array.from(selections.keys())
    .sort((a, b) => a - b)
    .forEach((characterId) => {
      const costumeIds = Array.from(selections.get(characterId) || []).sort((a, b) => a - b);
      costumeIds.forEach((costumeId) => {
        pairs.push(`${characterId}:${costumeId}`);
      });
    });
  return pairs.join(",");
}

// Drops costume picks for characters no longer selected, and costumes that
// `getCostumeIds(characterId)` says don't exist.
export function pruneCostumeSelection(costumeValue, selectedCharacterIds, getCostumeIds) {
  const selectedSet = new Set(selectedCharacterIds);
  const selections = parseCostumeSelection(costumeValue);
  const pruned = new Map();

  selections.forEach((costumeIds, characterId) => {
    if (!selectedSet.has(characterId)) {
      return;
    }
    const available = new Set(getCostumeIds(characterId));
    const validCostumes = Array.from(costumeIds).filter((costumeId) => available.has(costumeId));
    if (validCostumes.length > 0) {
      pruned.set(characterId, new Set(validCostumes));
    }
  });

  return serializeCostumeSelection(pruned);
}

const formatRankName = (rankName) => rankName.replace(/_/g, " ");

const splitList = (value) =>
  value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

// Lists up to two values, then a count.
function summarizeList(values) {
  return values.length <= 2 ? values.join(", ") : `${values.length} selected`;
}

// "2026-10-01" -> "Oct 1, 2026", read as a calendar date (no time zone shift).
function formatFilterDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return value;
  }
  return new Date(year, month - 1, day).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const FILTER_DESCRIPTIONS = {
  keyword: (value) => `“${value}”`,
  player: (value) => `Player: ${value}`,
  repository: (value) => `Repository: ${summarizeList(splitList(value))}`,
  tournament: (value) => `Tournament: ${summarizeList(splitList(value))}`,
  source: (value) => `Source: ${summarizeList(splitList(value))}`,
  character: (value) => {
    const names = parseSelectedCharacterIds(value).map((id) => CHARACTER_BY_ID.get(id).name);
    return names.length > 0 ? summarizeList(names) : null;
  },
  costume: (value) => {
    let count = 0;
    parseCostumeSelection(value).forEach((costumeIds) => {
      count += costumeIds.size;
    });
    return count > 0 ? `${count} ${count === 1 ? "costume" : "costumes"}` : null;
  },
  rank: (value) => `Rank: ${splitList(value).map(formatRankName).join(" to ")}`,
  min_rank: (value) => `Rating ${value}+`,
  max_rank: (value) => `Rating up to ${value}`,
  ranked: (value) => `Ranked: ${value}`,
  include_handwarmers: () => "With hand warmers",
  date_from: (value) => `From ${formatFilterDate(value)}`,
  date_to: (value) => `Until ${formatFilterDate(value)}`,
};

// One { key, label } per active filter, in INITIAL_FILTERS order, for the chip row.
export function describeActiveFilters(filters) {
  return Object.keys(INITIAL_FILTERS).flatMap((key) => {
    const value = filters[key];
    if (!value) {
      return [];
    }
    const label = FILTER_DESCRIPTIONS[key](value);
    return label ? [{ key, label }] : [];
  });
}
