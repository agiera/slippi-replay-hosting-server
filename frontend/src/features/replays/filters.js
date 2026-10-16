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
