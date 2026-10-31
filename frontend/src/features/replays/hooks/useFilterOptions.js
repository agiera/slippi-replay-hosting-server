import { useEffect, useState } from "react";

import { fetchReplayFilterOptions } from "../../../lib/api/replays";

const EMPTY_OPTIONS = { repositories: [], tournaments: [], sources: [] };

const asList = (value) => (Array.isArray(value) ? value : []);

// Repository / tournament / source names for the top filter bar. Empty on failure.
export function useFilterOptions() {
  const [options, setOptions] = useState(EMPTY_OPTIONS);

  useEffect(() => {
    let cancelled = false;

    fetchReplayFilterOptions()
      .then((data) => {
        if (!cancelled) {
          setOptions({
            repositories: asList(data.repositories),
            tournaments: asList(data.tournaments),
            sources: asList(data.sources),
          });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setOptions(EMPTY_OPTIONS);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return options;
}
