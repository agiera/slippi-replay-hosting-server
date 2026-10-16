import { crownImage, getCharacterStock, getPortIcon, getRankImage } from "../../../assets";
import { getPlayerDisplay } from "../players";

const PORT_SLOTS = [1, 2, 3, 4];

// One player column. Live and completed rows share the same normalized player
// shape. `player` is null for padded slots (rows with fewer players than columns).
export function PlayerCell({ player }) {
  if (!player) {
    return <div className="min-h-[100px]" />;
  }

  const characterImage = getCharacterStock(player.character_id, player.costume_id ?? player.character_color);
  const rankImage = getRankImage(player.rank);
  const { displayName, connectCode, rating, isWinner, isCpu } = getPlayerDisplay(player);

  return (
    <div className="grid min-h-[100px] content-center gap-[5px]">
      <div className="flex items-center gap-1.5">
        <div className="font-semibold text-fg">
          {displayName}
          {isCpu ? " [CPU]" : ""}
        </div>
        {isWinner ? <img src={crownImage} alt="Winner" className="size-[13px] object-contain" /> : null}
      </div>
      <div className="text-[0.75rem] tracking-[0.02em] text-subtle">{connectCode}</div>
      <div className="flex items-center gap-2">
        <div className="flex size-[26px] items-center justify-center">
          {characterImage ? <img src={characterImage} alt="Character" className="max-h-full max-w-full object-contain" /> : "-"}
        </div>
        <div className="flex size-[26px] items-center justify-center">
          {rankImage ? <img src={rankImage} alt="Rank" className="max-h-full max-w-full object-contain" /> : "-"}
        </div>
        <div className="text-[0.84rem] font-semibold text-subtle">{rating}</div>
      </div>
      <div className="flex gap-1">
        {PORT_SLOTS.map((slot) => {
          const icon = getPortIcon(player.port ?? null, slot);
          return icon ? <img key={slot} src={icon} alt={`Port ${slot}`} className="size-3.5 opacity-95" /> : null;
        })}
      </div>
    </div>
  );
}
