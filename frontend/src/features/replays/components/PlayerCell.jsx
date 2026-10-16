import { crownImage, getCharacterStock, getRankImage } from "../../../assets";
import { cn } from "../../../lib/cn";
import { getPlayerDisplay } from "../players";

const PORT_SLOTS = [1, 2, 3, 4];
// The player's own port dot is lit in its controller colour; the others stay grey.
const PORT_DOT_COLORS = { 1: "bg-p1", 2: "bg-p2", 3: "bg-p3", 4: "bg-p4" };

// One player. Live and completed rows share the same normalized player shape.
export function PlayerCell({ player }) {
  const port = PORT_SLOTS.includes(Number(player.port)) ? Number(player.port) : null;
  const characterImage = getCharacterStock(player.character_id, player.costume_id ?? player.character_color);
  const rankImage = getRankImage(player.rank);
  const { displayName, connectCode, rating, isWinner, isCpu } = getPlayerDisplay(player);
  const name = isCpu && displayName === "-" ? "CPU" : displayName;

  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <div className="flex size-8 shrink-0 items-center justify-center">
        {characterImage ? (
          <img src={characterImage} alt="" className="size-8 object-contain [image-rendering:pixelated]" />
        ) : null}
      </div>
      <div className="grid min-w-0 gap-px">
        <div className="flex min-w-0 items-center gap-1">
          <span className="truncate font-semibold text-fg" title={name}>
            {name}
          </span>
          {isCpu && name !== "CPU" ? <span className="shrink-0 text-[0.72rem] text-muted">CPU</span> : null}
          {isWinner ? <img src={crownImage} alt="Winner" title="Winner" className="size-3.5 shrink-0 object-contain" /> : null}
        </div>
        {isCpu ? null : <div className="truncate text-[0.76rem] text-subtle">{connectCode}</div>}
        {rankImage || player.rating != null ? (
          <div className="flex items-center gap-1 text-[0.8rem] font-medium text-subtle tabular-nums">
            {rankImage ? (
              <img src={rankImage} alt={String(player.rank).replace(/_/g, " ")} className="size-4 object-contain" />
            ) : null}
            {rating}
          </div>
        ) : null}
        <div className="mt-1 flex gap-1" role="img" aria-label={port ? `Port ${port}` : "Port unknown"}>
          {PORT_SLOTS.map((slot) => (
            <span
              key={slot}
              className={cn("size-[7px] rounded-full", slot === port ? PORT_DOT_COLORS[slot] : "bg-muted/30")}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
