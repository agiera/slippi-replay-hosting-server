import { useCallback, useMemo, useState } from "react";

import { FilterSidebar } from "../features/replays/components/FilterSidebar";
import { FilterToolbar } from "../features/replays/components/FilterToolbar";
import { ReplayList } from "../features/replays/components/ReplayList";
import { TopFilterBar } from "../features/replays/components/TopFilterBar";
import { describeActiveFilters } from "../features/replays/filters";
import { useFilterOptions } from "../features/replays/hooks/useFilterOptions";
import { useLiveStream } from "../features/replays/hooks/useLiveStream";
import { useNow } from "../features/replays/hooks/useNow";
import { useReplayFeed } from "../features/replays/hooks/useReplayFeed";
import { useReplayFilters } from "../features/replays/hooks/useReplayFilters";
import { mergeReplayRows } from "../features/replays/state/rowLifecycle";

export default function Home() {
  const { filters, debouncedFilters, setFilter, setCharacters, resetFilters } = useReplayFilters();
  const filterOptions = useFilterOptions();
  const feed = useReplayFeed(debouncedFilters);
  const live = useLiveStream({
    onReplaysChanged: feed.reload,
    onTerminalRow: feed.preserveTerminalRow,
  });
  const nowMs = useNow(1000);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const closeFilters = useCallback(() => setFiltersOpen(false), []);

  // Live stream rows first, then completed replays; a live row is swapped for
  // its completed replay once that lands in the feed.
  const rows = useMemo(
    () => mergeReplayRows({
      streamStatus: live.streamStatus,
      files: feed.files,
      nowMs,
      includeLiveRows: true,
      preservedTerminalRows: feed.preservedTerminalRows,
    }),
    [live.streamStatus, feed.files, nowMs, feed.preservedTerminalRows],
  );

  // Clearing characters also clears their costume picks.
  const removeFilter = (key) => (key === "character" ? setCharacters("") : setFilter(key, ""));

  return (
    <main className="block min-h-[calc(100vh-46px)] px-2 pb-7">
      <TopFilterBar filters={filters} options={filterOptions} setFilter={setFilter} />

      <div className="mx-auto mt-3 grid w-[min(1080px,100%)] grid-cols-1 items-start gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
        <FilterSidebar
          filters={filters}
          setFilter={setFilter}
          setCharacters={setCharacters}
          resetFilters={resetFilters}
          open={filtersOpen}
          onClose={closeFilters}
        />

        <section className="w-full min-w-0" aria-label="Replays">
          <FilterToolbar
            filters={filters}
            onOpenFilters={() => setFiltersOpen(true)}
            onRemoveFilter={removeFilter}
            onClearAll={resetFilters}
          />

          {feed.error ? (
            <p className="text-danger">{feed.error}</p>
          ) : (
            <ReplayList
              rows={rows}
              isInitialLoading={feed.isInitialLoading}
              hasFilters={describeActiveFilters(debouncedFilters).length > 0}
              nowMs={nowMs}
              followSource={live.followSource}
              onFollow={live.followInSlippi}
              onStopFollowing={live.stopFollowing}
            />
          )}

          {live.streamError ? <p className="text-danger">{live.streamError}</p> : null}

          <div ref={feed.sentinelRef} className="h-0.5" />
          {feed.loading && feed.files.length > 0 ? <p className="text-center text-muted">Loading more replays…</p> : null}
          {!feed.hasMore && feed.files.length > 0 ? <p className="text-center text-[0.88rem] text-muted">That’s every replay.</p> : null}
        </section>
      </div>
    </main>
  );
}
