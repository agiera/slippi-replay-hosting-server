import { getStageImage } from "../../../assets";
import { cn } from "../../../lib/cn";
import { formatGameDuration, formatPlayedDateTime, formatStageName } from "../../../lib/format";
import { getRowPlayers } from "../players";
import { LivePill } from "./LivePill";
import { PlayerCell } from "./PlayerCell";
import { RowActions } from "./RowActions";

export function ReplayRow({ row, playerColumnCount, followSource, onFollow, onStopFollowing }) {
  const isStreaming = row.lifecycle === "live" || row.lifecycle === "finalizing";
  const stageImage = getStageImage(row.stage);

  const rowPlayers = getRowPlayers(row).slice(0, playerColumnCount);
  const paddedPlayers = [
    ...rowPlayers,
    ...Array.from({ length: Math.max(0, playerColumnCount - rowPlayers.length) }, () => null),
  ];
  // A live game may not have a parsed stage yet.
  const stageLabel = row.stage === null || row.stage === undefined
    ? (isStreaming ? "Streaming" : "-")
    : formatStageName(row.stage);

  return (
    <tr
      className={cn("[&>td]:h-[120px]", stageImage && "stage-backdrop")}
      style={stageImage ? { "--stage-img": `url(${stageImage})` } : undefined}
    >
      <td>
        <div className="grid min-h-[100px] w-[110px] content-center gap-1">
          {isStreaming ? <LivePill>{row.lifecycle === "finalizing" ? "FINALIZING" : "LIVE"}</LivePill> : null}
          <div className="leading-tight font-bold text-fg">{row.repository_label || "-"}</div>
          <div className="text-[0.78rem] leading-tight text-subtle">{row.source_label || "-"}</div>
        </div>
      </td>
      {paddedPlayers.map((player, idx) => (
        <td key={`player-col-${idx}`}>
          <PlayerCell player={player} />
        </td>
      ))}
      <td>
        <div className="grid min-h-[100px] content-center gap-1">
          <div className="leading-tight font-semibold text-fg">{stageLabel}</div>
          <div className="text-[0.82rem] leading-tight text-subtle">{formatGameDuration(row.game_duration)}</div>
          <div className="text-[0.82rem] leading-tight text-subtle">{formatPlayedDateTime(row.start_datetime)}</div>
        </div>
      </td>
      <td>
        <RowActions row={row} followSource={followSource} onFollow={onFollow} onStopFollowing={onStopFollowing} />
      </td>
    </tr>
  );
}
