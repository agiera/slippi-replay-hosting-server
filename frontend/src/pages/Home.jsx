import { useMemo } from "react";

import { FilterSidebar } from "../features/replays/components/FilterSidebar";
import { ReplayTable } from "../features/replays/components/ReplayTable";
import { TopFilterBar } from "../features/replays/components/TopFilterBar";
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

  return (
    <main className="block min-h-[calc(100vh-46px)] px-2 pb-7">
      <TopFilterBar filters={filters} options={filterOptions} setFilter={setFilter} />

      <div className="mx-auto mt-3 grid w-[min(1080px,100%)] grid-cols-1 items-start gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
        <FilterSidebar
          filters={filters}
          setFilter={setFilter}
          setCharacters={setCharacters}
          resetFilters={resetFilters}
        />

        <section className="w-full">
          {feed.error ? (
            <p className="text-danger">{feed.error}</p>
          ) : (
            <ReplayTable
              rows={rows}
              isInitialLoading={feed.isInitialLoading}
              followSource={live.followSource}
              onFollow={live.followInSlippi}
              onStopFollowing={live.stopFollowing}
            />
          )}

          {live.streamError ? <p className="text-danger">{live.streamError}</p> : null}

          <div ref={feed.sentinelRef} className="h-0.5" />
          {feed.loading && feed.files.length > 0 ? <p>Loading more...</p> : null}
          {!feed.hasMore && feed.files.length > 0 ? <p className="mt-0 text-muted">End of results.</p> : null}
        </section>
      </div>
    </main>
  );
}
