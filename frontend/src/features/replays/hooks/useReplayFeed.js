import { useCallback, useEffect, useRef, useState } from "react";

import { fetchReplayFiles } from "../../../lib/api/replays";

const PAGE_SIZE = 40;

/**
 * Cursor-paginated replay list for `filters`. Reloads when filters change and
 * loads the next page when `sentinelRef`'s element scrolls into view.
 *
 * Also tracks `preservedTerminalRows`: keys of just-ended live rows to keep on
 * screen until the next first-page load brings in their completed replays.
 */
export function useReplayFeed(filters) {
  const [files, setFiles] = useState([]);
  const [cursor, setCursor] = useState(null);
  // No pagination until a first page supplies a cursor.
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preservedTerminalRows, setPreservedTerminalRows] = useState([]);
  const sentinelRef = useRef(null);
  // `loading` is stale inside an IntersectionObserver callback created before the
  // latest render; without this synchronous flag a "load more" can start next to
  // a first-page load and append the same page a second time.
  const inFlightRef = useRef(false);
  // Bumped by every first-page load so superseded requests drop their results.
  const generationRef = useRef(0);

  const reload = useCallback(async () => {
    const generation = ++generationRef.current;
    inFlightRef.current = true;
    setLoading(true);
    setError("");
    try {
      const data = await fetchReplayFiles({ ...filters, limit: PAGE_SIZE });
      if (generation !== generationRef.current) {
        return;
      }
      const nextCursor = data?.next_cursor ?? null;
      setFiles(data.items);
      setCursor(nextCursor);
      setHasMore(nextCursor !== null);
    } catch (err) {
      if (generation === generationRef.current) {
        setError(err.message);
        setHasMore(false);
      }
    } finally {
      if (generation === generationRef.current) {
        inFlightRef.current = false;
        setPreservedTerminalRows([]);
        setLoading(false);
      }
    }
  }, [filters]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!sentinelRef.current) {
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      if (!entries[0].isIntersecting || inFlightRef.current || !hasMore || error) {
        return;
      }

      async function loadMore() {
        const generation = generationRef.current;
        inFlightRef.current = true;
        setLoading(true);
        setError("");
        try {
          const data = await fetchReplayFiles({ ...filters, limit: PAGE_SIZE, cursor });
          if (generation !== generationRef.current) {
            return;
          }
          const nextCursor = data?.next_cursor ?? null;
          setFiles((prev) => {
            const seen = new Set(prev.map((file) => file.id));
            return [...prev, ...data.items.filter((file) => !seen.has(file.id))];
          });
          setCursor(nextCursor);
          // Stop auto-pagination if server does not provide a cursor or repeats it.
          setHasMore(nextCursor !== null && nextCursor !== cursor);
        } catch (err) {
          if (generation === generationRef.current) {
            setError(err.message);
            setHasMore(false);
          }
        } finally {
          if (generation === generationRef.current) {
            inFlightRef.current = false;
            setLoading(false);
          }
        }
      }

      loadMore();
    });

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [filters, cursor, hasMore, loading, error]);

  const preserveTerminalRow = useCallback((rowKey) => {
    setPreservedTerminalRows((prev) => (prev.includes(rowKey) ? prev : [...prev, rowKey]));
  }, []);

  return {
    files,
    loading,
    error,
    hasMore,
    isInitialLoading: loading && files.length === 0,
    reload,
    sentinelRef,
    preservedTerminalRows,
    preserveTerminalRow,
  };
}
