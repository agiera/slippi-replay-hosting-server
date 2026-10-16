import { getStageImage } from "../../../assets";
import { cn } from "../../../lib/cn";
import { formatGameDuration, formatPlayedDateTime, formatRelativeTime, formatStageName } from "../../../lib/format";
import { getRowPlayers } from "../players";
import { LivePill } from "./LivePill";
import { PlayerCell } from "./PlayerCell";
import { RowActions } from "./RowActions";

// Desktop columns: where/source | players (two per line) | stage and time | actions.
// Below `md` the row stacks: where + stage on top, players in two columns, actions last.
export const ROW_GRID =
  "grid grid-cols-2 items-center gap-x-4 gap-y-3 px-3 py-3 " +
  "md:grid-cols-[6.5rem_minmax(0,1fr)_7.5rem_8.5rem] md:py-4";

export const PLAYER_GROUP =
  "col-span-2 grid grid-cols-2 gap-x-4 gap-y-3 max-md:order-1 md:col-span-1";

export function ReplayRow({ row, nowMs, followSource, onFollow, onStopFollowing }) {
  const isStreaming = row.lifecycle === "live" || row.lifecycle === "finalizing";
  const stageImage = getStageImage(row.stage);

  const players = getRowPlayers(row).slice(0, 4);
  // A live game may not have a parsed stage yet.
  const stageLabel = row.stage === null || row.stage === undefined
    ? (isStreaming ? "Picking stage" : "Unknown stage")
    : formatStageName(row.stage);
  const hasDuration = row.game_duration !== null && row.game_duration !== undefined;

  return (
    <li
      className={cn(ROW_GRID, "border-b border-accent/40 bg-clip-padding last:border-b-0", stageImage && "stage-backdrop")}
      style={stageImage ? { "--stage-img": `url(${stageImage})` } : undefined}
    >
      <div className="grid min-w-0 content-center gap-0.5">
        {isStreaming ? (
          <div className="mb-0.5">
            <LivePill>{row.lifecycle === "finalizing" ? "Finalizing" : "Live"}</LivePill>
          </div>
        ) : null}
        <div className="truncate leading-tight font-bold text-fg" title={row.repository_label || undefined}>
          {row.repository_label || "-"}
        </div>
        <div className="truncate text-[0.78rem] leading-tight text-subtle">{row.source_label || "-"}</div>
      </div>

      <div className={PLAYER_GROUP}>
        {players.map((player, idx) => (
          <PlayerCell key={`player-${player.port ?? idx}`} player={player} />
        ))}
      </div>

      <div className="grid min-w-0 content-center gap-0.5 max-md:text-right">
        <div className="line-clamp-2 leading-tight font-semibold text-fg" title={stageLabel}>
          {stageLabel}
        </div>
        {hasDuration ? (
          <div className="text-[0.8rem] leading-tight text-subtle tabular-nums">{formatGameDuration(row.game_duration)}</div>
        ) : null}
        {row.start_datetime ? (
          <time
            dateTime={row.start_datetime}
            title={formatPlayedDateTime(row.start_datetime)}
            className="text-[0.8rem] leading-tight text-subtle"
          >
            {formatRelativeTime(row.start_datetime, nowMs)}
          </time>
        ) : null}
      </div>

      <div className="col-span-2 max-md:order-2 md:col-span-1">
        <RowActions row={row} followSource={followSource} onFollow={onFollow} onStopFollowing={onStopFollowing} />
      </div>
    </li>
  );
}
