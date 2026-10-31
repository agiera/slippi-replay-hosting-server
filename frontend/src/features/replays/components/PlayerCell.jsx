import { crownImage, getCharacterStock, getRankImage } from "../../../assets";
import { getPlayerDisplay } from "../players";
import { PlayerLink } from "./PlayerLink";

// One player: stock icon beside two lines (name, then code and rank). Port and
// other details are in the tooltip; players with a connect code link to their
// slippi.gg profile. Live and completed rows share the same player shape.
export function PlayerCell({ player }) {
  const characterImage = getCharacterStock(player.character_id, player.costume_id ?? player.character_color);
  const rankImage = getRankImage(player.rank);
  const { displayName, connectCode, rating, isWinner, isCpu } = getPlayerDisplay(player);
  const name = isCpu && displayName === "-" ? "CPU" : displayName;
  const hasRank = Boolean(rankImage) || player.rating != null;

  return (
    <PlayerLink player={player} className="-m-1 flex min-w-0 items-center gap-3 p-1">
      <div className="flex size-9 shrink-0 items-center justify-center">
        {characterImage ? <img src={characterImage} alt="" className="pixelated size-9 object-contain" /> : null}
      </div>
      <div className="grid min-w-0 gap-0.5">
        <div className="flex min-w-0 items-center gap-1">
          <span className="truncate text-sm font-semibold text-white">{name}</span>
          {isCpu && name !== "CPU" ? <span className="shrink-0 text-xs text-gray-400">CPU</span> : null}
          {isWinner ? <img src={crownImage} alt="Winner" className="size-3.5 shrink-0 object-contain" /> : null}
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-400">
          {isCpu ? null : <span className="truncate">{connectCode}</span>}
          {hasRank ? (
            <span className="flex shrink-0 items-center gap-1 font-medium text-gray-300 tabular-nums">
              {rankImage ? (
                <img src={rankImage} alt={String(player.rank).replace(/_/g, " ")} className="size-4 object-contain" />
              ) : null}
              {rating}
            </span>
          ) : null}
        </div>
      </div>
    </PlayerLink>
  );
}
