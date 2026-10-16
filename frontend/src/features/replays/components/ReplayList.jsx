import { cn } from "../../../lib/cn";
import { PLAYER_GROUP, ROW_GRID, ReplayRow } from "./ReplayRow";

const SKELETON_ROWS = 6;

export function ReplayList({ rows, isInitialLoading, hasFilters, nowMs, followSource, onFollow, onStopFollowing }) {
  if (!isInitialLoading && rows.length === 0) {
    return (
      <div className="bg-surface px-5 py-10 text-center">
        <p className="m-0 font-semibold text-fg">No replays found</p>
        <p className="m-0 mt-1 text-[0.9rem] text-muted">
          {hasFilters ? "Try removing a filter." : "Replays appear here once a Wii uploads them."}
        </p>
      </div>
    );
  }

  return (
    <ul
      className="m-0 list-none bg-surface p-0"
      aria-busy={isInitialLoading || undefined}
    >
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
  return (
    <div
      className={cn(
        "relative h-3 overflow-hidden rounded-full bg-accent/22",
        "after:absolute after:inset-0 after:-translate-x-full after:animate-shimmer motion-reduce:after:animate-none",
        "after:bg-linear-to-r after:from-white/0 after:via-white/20 after:to-white/0",
        className,
      )}
    />
  );
}

function SkeletonRows() {
  return Array.from({ length: SKELETON_ROWS }).map((_, rowIdx) => (
    <li key={`loading-${rowIdx}`} className={cn(ROW_GRID, "border-b border-accent/40 bg-clip-padding last:border-b-0")} aria-hidden="true">
      <div className="grid gap-2">
        <SkeletonBar className="w-[80%]" />
        <SkeletonBar className="w-[50%]" />
      </div>
      <div className={PLAYER_GROUP}>
        {Array.from({ length: 2 }).map((__, idx) => (
          <div key={idx} className="flex items-center gap-2.5">
            <div className="size-8 shrink-0 rounded-full bg-accent/22" />
            <div className="grid flex-1 gap-2">
              <SkeletonBar className="w-[70%]" />
              <SkeletonBar className="w-[45%]" />
            </div>
          </div>
        ))}
      </div>
      <div className="grid gap-2 max-md:justify-items-end">
        <SkeletonBar className="w-[75%]" />
        <SkeletonBar className="w-[40%]" />
      </div>
      <div className="col-span-2 max-md:order-2 md:col-span-1">
        <SkeletonBar className="h-7 w-full rounded-lg" />
      </div>
    </li>
  ));
}
