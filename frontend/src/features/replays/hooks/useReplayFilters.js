import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getCostumeIds } from "../../../assets";
import {
  INITIAL_FILTERS,
  buildSearchParams,
  parseFiltersFromSearch,
  parseSelectedCharacterIds,
  pruneCostumeSelection,
} from "../filters";

const DEBOUNCE_MS = 500;

/**
 * Filter state mirrored to the URL. `filters` updates on every keystroke;
 * `debouncedFilters` settles 500ms later and is what queries and the URL use.
 */
export function useReplayFilters() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState(() => parseFiltersFromSearch(searchParams));
  const [debouncedFilters, setDebouncedFilters] = useState(filters);

  // Adopt filters from the URL on back/forward navigation.
  useEffect(() => {
    const nextFilters = parseFiltersFromSearch(searchParams);
    if (JSON.stringify(nextFilters) !== JSON.stringify(filters)) {
      setFilters(nextFilters);
      setDebouncedFilters(nextFilters);
    }
  }, [searchParams]);

  useEffect(() => {
    const timeoutId = setTimeout(() => setDebouncedFilters(filters), DEBOUNCE_MS);
    return () => clearTimeout(timeoutId);
  }, [filters]);

  useEffect(() => {
    const nextParams = buildSearchParams(debouncedFilters);
    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [debouncedFilters, searchParams, setSearchParams]);

  const setFilter = useCallback((name, value) => {
    setFilters((prev) => ({ ...prev, [name]: value }));
  }, []);

  // Changing characters also drops costume picks for characters no longer selected.
  const setCharacters = useCallback((nextCharacterValue) => {
    const nextCharacterIds = parseSelectedCharacterIds(nextCharacterValue);
    setFilters((prev) => ({
      ...prev,
      character: nextCharacterValue,
      costume: pruneCostumeSelection(prev.costume, nextCharacterIds, getCostumeIds),
    }));
  }, []);

  const resetFilters = useCallback(() => setFilters(INITIAL_FILTERS), []);

  return { filters, debouncedFilters, setFilter, setCharacters, resetFilters };
}
