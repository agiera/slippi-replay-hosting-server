"""Lifecycle helpers for rendered mp4 outputs.

Rendered videos expire after ``RENDER_OUTPUT_TTL_SECONDS`` (default 30 days).
Viewing a VOD refreshes its expiry, so frequently watched videos stick around
while forgotten ones are pruned from disk and reset so they can be re-requested.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.render_job import RenderJob

_last_pruned_at: datetime | None = None


def _ttl_seconds() -> int:
    return max(0, int(settings.RENDER_OUTPUT_TTL_SECONDS))


def new_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=_ttl_seconds())


def requeue_orphaned_jobs(db: Session) -> None:
    # On startup no workers are connected, so any job left mid-flight by a crash
    # or restart is stale; send it back to pending so it is dispatched again
    # instead of hanging forever in "dispatched"/"rendering".
    stale = db.scalars(
        select(RenderJob).where(RenderJob.status.in_(("dispatched", "rendering")))
    ).all()
    for job in stale:
        job.status = "pending"
        job.worker_token_id = None
        job.claimed_at = None
        job.output_size_bytes = 0
    if stale:
        db.commit()


def output_path(folder: str, name: str) -> Path:
    return Path(settings.RENDER_STORAGE_DIR) / folder / name


def refresh_expiry(db: Session, job: RenderJob) -> None:
    if job.status != "completed" or not job.output_name:
        return
    job.expires_at = new_expiry()
    db.commit()


def _clear_output(job: RenderJob) -> None:
    if job.output_folder and job.output_name:
        candidate = output_path(job.output_folder, job.output_name)
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass
    job.status = "expired"
    job.output_folder = None
    job.output_name = None
    job.output_size_bytes = None
    job.expires_at = None


def prune_expired_outputs(db: Session, force: bool = False) -> None:
    global _last_pruned_at

    now = datetime.now(timezone.utc)
    interval = max(0, int(settings.RENDER_OUTPUT_PRUNE_INTERVAL_SECONDS))

    if not force and _last_pruned_at is not None:
        if (now - _last_pruned_at).total_seconds() < interval:
            return

    expired = db.scalars(
        select(RenderJob).where(
            RenderJob.status == "completed",
            RenderJob.expires_at.is_not(None),
            RenderJob.expires_at < now,
        )
    ).all()

    for job in expired:
        _clear_output(job)

    if expired:
        db.commit()

    _last_pruned_at = now
