import { useMemo } from "react";

import { cn } from "../../../lib/cn";
import { getRowPlayers } from "../players";
import { ReplayRow } from "./ReplayRow";

const SKELETON_ROWS = 6;
const SKELETON_WIDTHS = ["w-[72%]", "w-[90%]", "w-[90%]", "w-[72%]", "w-[54%]"];

// Show 2–4 player columns, as many as the widest row needs.
function getPlayerColumnCount(rows) {
  const maxPlayers = rows.reduce((maxCount, row) => Math.max(maxCount, getRowPlayers(row).length), 0);
  return Math.min(4, Math.max(2, maxPlayers));
}

export function ReplayTable({ rows, isInitialLoading, followSource, onFollow, onStopFollowing }) {
  const playerColumnCount = useMemo(() => getPlayerColumnCount(rows), [rows]);

  return (
    <div className="overflow-auto">
      <table
        className={cn(
          "w-full border-collapse bg-surface",
          "[&_td]:border-b [&_td]:border-accent/22 [&_td]:px-3 [&_td]:py-2.5",
          "[&_td]:text-left [&_td]:align-middle [&_td]:text-[0.92rem]",
        )}
      >
        <tbody>
          {isInitialLoading ? <SkeletonRows /> : null}
          {!isInitialLoading && rows.length === 0 ? (
            <tr>
              <td colSpan={playerColumnCount + 3}>No files found.</td>
            </tr>
          ) : null}
          {rows.map((row) => (
            <ReplayRow
              key={row.rowKey}
              row={row}
              playerColumnCount={playerColumnCount}
              followSource={followSource}
              onFollow={onFollow}
              onStopFollowing={onStopFollowing}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SkeletonRows() {
  return Array.from({ length: SKELETON_ROWS }).map((_, rowIdx) => (
    <tr key={`loading-${rowIdx}`} className="[&_td]:bg-surface/90">
      {SKELETON_WIDTHS.map((width, cellIdx) => (
        <td key={cellIdx}>
          <div
            className={cn(
              "relative h-3.5 overflow-hidden rounded-full bg-accent/22",
              "after:absolute after:inset-0 after:-translate-x-full after:animate-shimmer",
              "after:bg-linear-to-r after:from-white/0 after:via-white/34 after:to-white/0",
              width,
            )}
          />
        </td>
      ))}
    </tr>
  ));
}
