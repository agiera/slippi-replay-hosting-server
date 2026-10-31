import { useId } from "react";

import { cn } from "../../../lib/cn";
import { buildSlippiProfileUrl } from "../../../lib/links";
import { getPlayerDisplay } from "../players";
import { PlayerTooltip } from "./PlayerTooltip";

// Wraps a player's display with their details tooltip, and links it to their
// slippi.gg profile (in a new tab) when they have a connect code. The link has no
// styling beyond hover and focus; `className` sets layout and padding.
export function PlayerLink({ player, className, children }) {
  const tooltipId = useId();
  const { isCpu } = getPlayerDisplay(player);
  const profileUrl = isCpu ? "" : buildSlippiProfileUrl(player.connect_code);
  const classes = cn("group relative rounded-md", className);

  if (!profileUrl) {
    return (
      <div className={classes} aria-describedby={tooltipId}>
        {children}
        <PlayerTooltip id={tooltipId} player={player} />
      </div>
    );
  }

  return (
    <a
      href={profileUrl}
      target="_blank"
      rel="noopener noreferrer"
      aria-describedby={tooltipId}
      className={cn(
        classes,
        "hover:bg-white/5 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-indigo-500",
      )}
    >
      {children}
      <PlayerTooltip id={tooltipId} player={player} />
    </a>
  );
}
