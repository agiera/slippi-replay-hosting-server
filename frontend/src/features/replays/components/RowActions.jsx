import { Button, ButtonLink } from "../../../components/ui/Button";
import { buildSlippiDeepLink, buildSlippiLabViewerUrl, resolveReplayDownloadUrl } from "../../../lib/links";

// Action buttons for a row: follow a live stream, wait while finalizing, or open/download a replay.
export function RowActions({ row, followSource, onFollow, onStopFollowing }) {
  return (
    <div className="flex min-h-[100px] flex-col items-start justify-center gap-1.5">
      {row.lifecycle === "live" ? (
        <LiveActions row={row} followSource={followSource} onFollow={onFollow} onStopFollowing={onStopFollowing} />
      ) : row.lifecycle === "finalizing" ? (
        <Button variant="secondary" size="sm" disabled>
          Finalizing...
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
      <Button variant="secondary" size="sm" onClick={() => onFollow(row.source_name, row.stream_game_id)}>
        {isFollowing ? "Following in Slippi" : "Stream in Slippi"}
      </Button>
      {isFollowing ? (
        <Button variant="secondary" size="sm" onClick={onStopFollowing}>
          Stop
        </Button>
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
      <ButtonLink
        size="sm"
        href={viewerHref || undefined}
        aria-disabled={!viewerHref || undefined}
        target="_blank"
        rel="noopener noreferrer"
      >
        View on SlippiLab
      </ButtonLink>
      <Button
        size="sm"
        disabled={!row.fileId}
        onClick={() => window.open(replayUrl, "_blank", "noopener,noreferrer")}
      >
        Download
      </Button>
    </>
  );
}
