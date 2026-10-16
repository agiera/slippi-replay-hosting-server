import { getStageImage } from "../../../assets";
import { Badge } from "../../../components/ui/Badge";
import { cn } from "../../../lib/cn";
import { formatGameDuration, formatPlayedDateTime, formatRelativeTime, formatStageName } from "../../../lib/format";
import { getRowPlayers, isTeamGame } from "../players";
import { PlayerCell } from "./PlayerCell";
import { RowActions } from "./RowActions";
import { TeamGroups } from "./TeamGroups";

// A 12-column grid. Desktop: where/source (2) | players (6) | stage and time (2) | actions (2).
// Players: two per line (1v1 and free-for-alls), or one line per team in team games.
// Below `md` the row stacks: where + stage side by side, then players, then actions.
export const ROW_GRID = "grid grid-cols-12 items-center gap-x-3 gap-y-4 bg-clip-padding px-4 py-4 sm:px-6";
export const META_CELL = "col-span-6 grid min-w-0 content-center gap-0.5 md:col-span-2";
export const PLAYER_GROUP = "col-span-12 grid grid-cols-2 gap-x-8 gap-y-3 max-md:order-1 md:col-span-6";
export const TEAM_GROUP = "col-span-12 max-md:order-1 md:col-span-6";
export const STAGE_CELL = "col-span-6 grid min-w-0 content-center gap-0.5 max-md:text-right md:col-span-2";
export const ACTION_CELL = "col-span-12 max-md:order-2 md:col-span-2";

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
      className={cn(ROW_GRID, stageImage && "stage-backdrop")}
      style={stageImage ? { "--stage-img": `url(${stageImage})` } : undefined}
    >
      <div className={META_CELL}>
        {isStreaming ? (
          <div className="mb-1">
            {row.lifecycle === "finalizing" ? (
              <Badge color="yellow" dot>Finalizing</Badge>
            ) : (
              <Badge color="red" dot>Live</Badge>
            )}
          </div>
        ) : null}
        <p className="truncate text-sm font-semibold text-white" title={row.repository_label || undefined}>
          {row.repository_label || "-"}
        </p>
        <p className="truncate text-xs text-gray-400">{row.source_label || "-"}</p>
      </div>

      {isTeamGame(row, players) ? (
        <TeamGroups players={players} className={TEAM_GROUP} />
      ) : (
        <div className={PLAYER_GROUP}>
          {players.map((player, idx) => (
            <PlayerCell key={`player-${player.port ?? idx}`} player={player} />
          ))}
        </div>
      )}

      <div className={STAGE_CELL}>
        <p className="line-clamp-2 text-sm font-medium text-white" title={stageLabel}>
          {stageLabel}
        </p>
        {hasDuration ? (
          <p className="text-xs text-gray-400 tabular-nums">{formatGameDuration(row.game_duration)}</p>
        ) : null}
        {row.start_datetime ? (
          <time
            dateTime={row.start_datetime}
            title={formatPlayedDateTime(row.start_datetime)}
            className="text-xs text-gray-400"
          >
            {formatRelativeTime(row.start_datetime, nowMs)}
          </time>
        ) : null}
      </div>

      <div className={ACTION_CELL}>
        <RowActions row={row} followSource={followSource} onFollow={onFollow} onStopFollowing={onStopFollowing} />
      </div>
    </li>
  );
}
