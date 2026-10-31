import { crownImage, getCharacterStock } from "../../../assets";
import { cn } from "../../../lib/cn";
import { getPlayerDisplay, groupPlayersByTeam } from "../players";
import { PlayerLink } from "./PlayerLink";

// Team names by team id, for screen readers.
const TEAM_NAMES = { 0: "Red team", 1: "Blue team", 2: "Green team" };

// One column per team (2v2, 1v3 or 2v1v1), set out like the two players of a 1v1.
const COLUMNS = { 2: "grid-cols-2", 3: "grid-cols-3" };

// Compact layout for team games: each team is a box of icon, name and connect code
// lines, with one crown on the winning team.
// Port, rank and rating are in the player tooltip to save space.
export function TeamGroups({ players, className }) {
  const teams = groupPlayersByTeam(players);

  return (
    <div className={cn("grid gap-x-4 gap-y-3", COLUMNS[teams.length] ?? "grid-cols-2", className)}>
      {teams.map(({ teamId, players: teamPlayers }) => {
        const isWinner = teamPlayers.some((player) => player.is_winner === 1);
        return (
          <div
            key={teamId}
            className="flex min-w-0 items-center gap-1 rounded-md bg-white/5 p-1 ring-1 ring-inset ring-white/10"
          >
            <ul className="grid min-w-0 flex-1" aria-label={TEAM_NAMES[teamId] ?? "Team"}>
              {teamPlayers.map((player, idx) => (
                <TeamPlayer key={player.port ?? idx} player={player} />
              ))}
            </ul>
            {isWinner ? <img src={crownImage} alt="Winning team" className="mr-1.5 size-4 shrink-0 object-contain" /> : null}
          </div>
        );
      })}
    </div>
  );
}

function TeamPlayer({ player }) {
  const characterImage = getCharacterStock(player.character_id, player.costume_id ?? player.character_color);
  const { displayName, isCpu } = getPlayerDisplay(player);
  const name = isCpu && displayName === "-" ? "CPU" : displayName;

  return (
    <li className="flex min-w-0">
      <PlayerLink player={player} className="flex min-w-0 flex-1 items-center gap-2 px-1.5 py-1">
        <div className="flex size-6 shrink-0 items-center justify-center">
          {characterImage ? <img src={characterImage} alt="" className="pixelated size-6 object-contain" /> : null}
        </div>
        <span className="truncate text-sm font-semibold text-white">{name}</span>
        {!isCpu && player.connect_code ? (
          <span className="w-0 min-w-0 flex-1 truncate text-xs text-gray-400">{player.connect_code}</span>
        ) : null}
      </PlayerLink>
    </li>
  );
}
