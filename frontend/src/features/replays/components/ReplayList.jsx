import { FunnelIcon } from "../../../components/ui/icons";
import { cn } from "../../../lib/cn";
import { ACTION_CELL, META_CELL, PLAYER_GROUP, ROW_GRID, STAGE_CELL, ReplayRow } from "./ReplayRow";

const SKELETON_ROWS = 6;

export function ReplayList({ rows, isInitialLoading, hasFilters, nowMs, followSource, onFollow, onStopFollowing }) {
  if (!isInitialLoading && rows.length === 0) {
    return (
      <div className="bg-gray-900 px-6 py-12 text-center">
        <FunnelIcon className="mx-auto size-8 text-gray-500" />
        <h3 className="mt-2 text-sm font-semibold text-white">No replays found</h3>
        <p className="mt-1 text-sm text-gray-400">
          {hasFilters ? "Try removing a filter." : "Replays appear here once a Wii uploads them."}
        </p>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-white/10 bg-gray-900" aria-busy={isInitialLoading || undefined}>
      {isInitialLoading ? <SkeletonRows /> : null}
      {rows.map((row) => (
        <ReplayRow
          key={row.rowKey}
          row={row}
          nowMs={nowMs}
          followSource={followSource}
          onFollow={onFollow}
          onStopFollowing={onStopFollowing}
        />
      ))}
    </ul>
  );
}

function SkeletonBar({ className }) {
  return <div className={cn("h-3 rounded-full bg-white/10", className)} />;
}

function SkeletonRows() {
  return Array.from({ length: SKELETON_ROWS }).map((_, rowIdx) => (
    <li key={`loading-${rowIdx}`} className={cn(ROW_GRID, "animate-pulse motion-reduce:animate-none")} aria-hidden="true">
      <div className={cn(META_CELL, "gap-2")}>
        <SkeletonBar className="w-4/5" />
        <SkeletonBar className="w-1/2" />
      </div>
      <div className={PLAYER_GROUP}>
        {Array.from({ length: 2 }).map((__, idx) => (
          <div key={idx} className="flex items-center gap-3">
            <div className="size-8 shrink-0 rounded-full bg-white/10" />
            <div className="grid flex-1 gap-2">
              <SkeletonBar className="w-2/3" />
              <SkeletonBar className="w-1/3" />
            </div>
          </div>
        ))}
      </div>
      <div className={cn(STAGE_CELL, "gap-2 max-md:justify-items-end")}>
        <SkeletonBar className="w-3/4" />
        <SkeletonBar className="w-2/5" />
      </div>
      <div className={ACTION_CELL}>
        <SkeletonBar className="h-7 w-full rounded-md" />
      </div>
    </li>
  ));
}
