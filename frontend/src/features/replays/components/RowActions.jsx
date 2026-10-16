import { Button, ButtonLink } from "../../../components/ui/Button";
import { buildSlippiDeepLink, buildSlippiLabViewerUrl, resolveReplayDownloadUrl } from "../../../lib/links";

const TEXT_LINK =
  "cursor-pointer rounded border-0 bg-transparent p-0 text-[0.8rem] font-semibold text-muted no-underline " +
  "underline-offset-2 hover:text-fg hover:underline aria-disabled:pointer-events-none aria-disabled:opacity-50";

// Actions for a row: follow a live stream, wait while finalizing, or open/download a replay.
// One button for the main action, smaller text links for the rest.
export function RowActions({ row, followSource, onFollow, onStopFollowing }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 md:grid md:justify-items-stretch">
      {row.lifecycle === "live" ? (
        <LiveActions row={row} followSource={followSource} onFollow={onFollow} onStopFollowing={onStopFollowing} />
      ) : row.lifecycle === "finalizing" ? (
        <Button variant="secondary" size="sm" disabled>
          Finalizing…
        </Button>
      ) : (
        <ReplayActions row={row} />
      )}
    </div>
  );
}

function LiveActions({ row, followSource, onFollow, onStopFollowing }) {
  const isFollowing = Boolean(followSource) && followSource === row.source_name;
  return (
    <>
      <Button
        variant={isFollowing ? "secondary" : "primary"}
        size="sm"
        onClick={() => onFollow(row.source_name, row.stream_game_id)}
      >
        {isFollowing ? "Following in Slippi" : "Stream in Slippi"}
      </Button>
      {isFollowing ? (
        <button type="button" className={TEXT_LINK} onClick={onStopFollowing}>
          Stop following
        </button>
      ) : null}
    </>
  );
}

function ReplayActions({ row }) {
  const replayUrl = resolveReplayDownloadUrl(row);
  const slippiHref = row.fileId ? buildSlippiDeepLink(replayUrl) : "";
  const viewerHref = buildSlippiLabViewerUrl(replayUrl);

  return (
    <>
      <ButtonLink size="sm" href={slippiHref || undefined} aria-disabled={!slippiHref || undefined}>
        View in Slippi
      </ButtonLink>
      <div className="flex gap-3 md:justify-center">
        <a
          className={TEXT_LINK}
          href={viewerHref || undefined}
          aria-disabled={!viewerHref || undefined}
          target="_blank"
          rel="noopener noreferrer"
        >
          SlippiLab
        </a>
        <a
          className={TEXT_LINK}
          href={row.fileId ? replayUrl : undefined}
          aria-disabled={!row.fileId || undefined}
          target="_blank"
          rel="noopener noreferrer"
        >
          Download
        </a>
      </div>
    </>
  );
}
