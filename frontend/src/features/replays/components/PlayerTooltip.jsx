import { getRankImage } from "../../../assets";
import { cn } from "../../../lib/cn";
import { getPlayerDetails } from "../players";

const PORT_SLOTS = [1, 2, 3, 4];
// The player's own port dot is lit in its controller colour; the others stay grey.
const PORT_DOT_COLORS = { 1: "bg-p1", 2: "bg-p2", 3: "bg-p3", 4: "bg-p4" };

// Card shown under a player on hover or keyboard focus. Its trigger needs the
// `group` class; `id` is referenced by the trigger's aria-describedby.
export function PlayerTooltip({ id, player }) {
  const details = getPlayerDetails(player);
  const rankImage = getRankImage(player.rank);

  return (
    <span
      id={id}
      role="tooltip"
      className={cn(
        "pointer-events-none absolute top-full left-0 z-40 mt-2 grid w-max max-w-64 gap-2 rounded-md bg-gray-800 px-3 py-2.5",
        "text-left text-xs shadow-lg ring-1 ring-white/10",
        "invisible opacity-0 transition-opacity duration-100 motion-reduce:transition-none",
        "group-hover:visible group-hover:opacity-100 group-focus-visible:visible group-focus-visible:opacity-100",
      )}
    >
      <span className="grid gap-0.5">
        <span className="text-sm font-semibold text-white">
          {details.name}
          {details.isCpu && details.name !== "CPU" ? <span className="ml-1 font-normal text-gray-400">CPU</span> : null}
        </span>
        {details.connectCode ? <span className="text-gray-400">{details.connectCode}</span> : null}
      </span>

      <span className="grid gap-1.5">
        {details.character ? <DetailRow label="Character">{details.character}</DetailRow> : null}
        <DetailRow label="Port">
          <span className="flex items-center gap-1">
            {PORT_SLOTS.map((slot) => (
              <span
                key={slot}
                aria-hidden="true"
                className={cn("size-2 rounded-full", slot === details.port ? PORT_DOT_COLORS[slot] : "bg-white/15")}
              />
            ))}
            <span className="ml-1">{details.port ? `P${details.port}` : "Unknown"}</span>
          </span>
        </DetailRow>
        {details.rankName || details.rating != null ? (
          <DetailRow label="Rank">
            <span className="flex items-center gap-1.5">
              {rankImage ? <img src={rankImage} alt="" className="size-4 object-contain" /> : null}
              {details.rankName}
              {details.rating != null ? <span className="text-gray-400 tabular-nums">{details.rating}</span> : null}
            </span>
          </DetailRow>
        ) : null}
      </span>
    </span>
  );
}

function DetailRow({ label, children }) {
  return (
    <span className="flex items-center gap-3">
      <span className="w-16 shrink-0 text-gray-400">{label}</span>
      <span className="text-gray-200">{children}</span>
    </span>
  );
}
