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
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preservedTerminalRows, setPreservedTerminalRows] = useState([]);
  const sentinelRef = useRef(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchReplayFiles({ ...filters, limit: PAGE_SIZE });
      const nextCursor = data?.next_cursor ?? null;
      setFiles(data.items);
      setCursor(nextCursor);
      setHasMore(nextCursor !== null);
    } catch (err) {
      setError(err.message);
      setHasMore(false);
    } finally {
      setPreservedTerminalRows([]);
      setLoading(false);
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
      if (!entries[0].isIntersecting || loading || !hasMore || error) {
        return;
      }

      async function loadMore() {
        setLoading(true);
        setError("");
        try {
          const data = await fetchReplayFiles({ ...filters, limit: PAGE_SIZE, cursor });
          const nextCursor = data?.next_cursor ?? null;
          setFiles((prev) => [...prev, ...data.items]);
          setCursor(nextCursor);
          // Stop auto-pagination if server does not provide a cursor or repeats it.
          setHasMore(nextCursor !== null && nextCursor !== cursor);
        } catch (err) {
          setError(err.message);
          setHasMore(false);
        } finally {
          setLoading(false);
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
