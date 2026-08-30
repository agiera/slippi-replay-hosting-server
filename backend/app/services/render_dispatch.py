"""In-memory dispatcher that pushes render jobs to connected worker daemons.

Worker daemons open a WebSocket to the server and opt in to rendering replays
into mp4 videos. Each worker advertises how many renders it can run at once
(``max_concurrent``, default 5, configurable from the client tray menu). The
server owns the queue: it keeps every pending job until capacity frees up and
fills each worker up to its declared concurrency. If a render fails, the worker
that reported the failure is placed in a cooldown so no new jobs are dispatched
to that host for five minutes.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import WebSocket
from sqlalchemy import func, or_, select

from app.db.session import SessionLocal
from app.models.render_job import RenderJob
from app.services.render_events import render_events

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENT = 5
# A render that genuinely fails is requeued after this delay until its attempts run out.
MAX_RENDER_ATTEMPTS = 3
RETRY_DELAY = timedelta(minutes=1)


def _clamp_concurrency(value: int | None) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_MAX_CONCURRENT
    if parsed < 1:
        return 1
    if parsed > 64:
        return 64
    return parsed


class WorkerConnection:
    def __init__(
        self,
        websocket: WebSocket,
        token_id: int,
        source_name: str,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        self.websocket = websocket
        self.token_id = token_id
        self.source_name = source_name
        self.max_concurrent = _clamp_concurrency(max_concurrent)
        self.active_job_ids: set[int] = set()

    @property
    def active_count(self) -> int:
        return len(self.active_job_ids)

    def available_slots(self) -> int:
        return max(0, self.max_concurrent - len(self.active_job_ids))

    async def send(self, payload: dict) -> None:
        await self.websocket.send_text(json.dumps(payload))


class RenderDispatcher:
    def __init__(self) -> None:
        self._workers: list[WorkerConnection] = []
        self._lock = asyncio.Lock()
        self._wakeup_task: asyncio.Task | None = None

    def has_workers(self) -> bool:
        return len(self._workers) > 0

    async def register(
        self,
        websocket: WebSocket,
        token_id: int,
        source_name: str,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> WorkerConnection:
        conn = WorkerConnection(websocket, token_id, source_name, max_concurrent)
        async with self._lock:
            self._workers.append(conn)
        logger.info(
            "Render worker connected (source=%s, max_concurrent=%d); total workers=%d",
            source_name,
            conn.max_concurrent,
            len(self._workers),
        )
        await self.dispatch_pending()
        return conn

    async def unregister(self, conn: WorkerConnection) -> None:
        async with self._lock:
            if conn in self._workers:
                self._workers.remove(conn)
            requeue_ids = list(conn.active_job_ids)
            conn.active_job_ids.clear()
        for job_id in requeue_ids:
            self._requeue_job(job_id)
        logger.info("Render worker disconnected (source=%s); total workers=%d", conn.source_name, len(self._workers))
        await self.dispatch_pending()

    async def update_config(self, conn: WorkerConnection, max_concurrent: int | None) -> None:
        async with self._lock:
            conn.max_concurrent = _clamp_concurrency(max_concurrent)
        logger.info(
            "Render worker (source=%s) set max_concurrent=%d",
            conn.source_name,
            conn.max_concurrent,
        )
        await self.dispatch_pending()

    def _pick_worker(self) -> WorkerConnection | None:
        candidates = [worker for worker in self._workers if worker.available_slots() > 0]
        if not candidates:
            return None
        # Spread load: prefer the worker with the fewest active jobs.
        return min(candidates, key=lambda worker: worker.active_count)

    async def dispatch_pending(self) -> None:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if self._pick_worker() is None:
                self._schedule_wakeup(now)
                return

            published_ids: list[int] = []
            db = SessionLocal()
            try:
                jobs = db.scalars(
                    select(RenderJob)
                    .where(RenderJob.status == "pending")
                    .where(or_(RenderJob.retry_at.is_(None), RenderJob.retry_at <= now))
                    .order_by(RenderJob.created_at)
                ).all()

                for job in jobs:
                    worker = self._pick_worker()
                    if worker is None:
                        break
                    job_id = job.id
                    replay_name = job.file.name if job.file else f"file-{job.file_id}.slp"
                    payload = {
                        "type": "render_job",
                        "job_id": job_id,
                        "file_id": job.file_id,
                        "replay_name": replay_name,
                        "download_path": f"/api/v1/replays/files/{job.file_id}/download",
                        "result_path": f"/api/v1/renders/jobs/{job_id}/result",
                    }
                    try:
                        await worker.send(payload)
                    except Exception:  # noqa: BLE001 - a broken socket is cleaned up on disconnect
                        logger.warning("Failed to dispatch job %d to worker; skipping", job_id)
                        continue

                    worker.active_job_ids.add(job_id)
                    job.status = "dispatched"
                    job.worker_token_id = worker.token_id
                    job.claimed_at = now
                    published_ids.append(job_id)

                db.commit()
            finally:
                db.close()

            for job_id in published_ids:
                render_events.publish(job_id)

            self._schedule_wakeup(now)

    def _schedule_wakeup(self, now: datetime) -> None:
        # Wake the queue once the earliest job retry timeout expires so requeued
        # work drains even when no other event triggers a dispatch.
        if self._wakeup_task is not None and not self._wakeup_task.done():
            return
        db = SessionLocal()
        try:
            next_retry = db.scalar(
                select(func.min(RenderJob.retry_at)).where(
                    RenderJob.status == "pending",
                    RenderJob.retry_at.is_not(None),
                    RenderJob.retry_at > now,
                )
            )
        finally:
            db.close()
        if next_retry is None:
            return
        delay = (next_retry - now).total_seconds()
        self._wakeup_task = asyncio.create_task(self._wakeup_after(delay))

    async def _wakeup_after(self, delay: float) -> None:
        await asyncio.sleep(max(0.0, delay) + 0.1)
        # Clear the handle before dispatching so the next retry deadline can be scheduled.
        self._wakeup_task = None
        await self.dispatch_pending()

    async def handle_worker_message(self, conn: WorkerConnection, message: dict) -> None:
        message_type = message.get("type")
        job_id = message.get("job_id")

        if message_type in {"worker_config", "worker_hello"}:
            await self.update_config(conn, message.get("max_concurrent"))
        elif message_type == "job_progress" and job_id:
            self._set_status(int(job_id), "rendering")
        elif message_type == "job_failed" and job_id:
            error = message.get("error")
            async with self._lock:
                conn.active_job_ids.discard(int(job_id))
            # "worker at capacity" is backpressure from a full worker, not a render
            # failure: requeue the job immediately so it retries without a timeout.
            if error == "worker at capacity":
                self._requeue_job(int(job_id))
                await self.dispatch_pending()
                return
            requeued = self._set_failed(int(job_id), error)
            logger.info(
                "Render job %s %s (source=%s)",
                job_id,
                "failed; will retry after timeout" if requeued else "failed",
                conn.source_name,
            )
            await self.dispatch_pending()
        elif message_type == "job_completed" and job_id:
            # Completion is authoritatively recorded by the REST result upload;
            # this only frees the slot so the next job can be dispatched.
            async with self._lock:
                conn.active_job_ids.discard(int(job_id))
            await self.dispatch_pending()

    async def on_job_finished(self, job_id: int) -> None:
        async with self._lock:
            for worker in self._workers:
                worker.active_job_ids.discard(job_id)
        await self.dispatch_pending()

    def _set_status(self, job_id: int, status: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(RenderJob, job_id)
            if job and job.status in {"dispatched", "rendering"}:
                # Count an attempt only when a render actually starts, so a capacity
                # rejection (which never renders) does not consume a retry.
                if status == "rendering" and job.status == "dispatched":
                    job.attempts += 1
                    job.retry_at = None
                job.status = status
                db.commit()
        finally:
            db.close()
        render_events.publish(job_id)

    def _set_failed(self, job_id: int, error: str | None) -> bool:
        requeued = False
        db = SessionLocal()
        try:
            job = db.get(RenderJob, job_id)
            if job and job.status in {"dispatched", "rendering", "pending"}:
                message = (error or "render failed")[:1000]
                if job.attempts < MAX_RENDER_ATTEMPTS:
                    # Requeue for a later retry rather than failing outright.
                    job.status = "pending"
                    job.error = message
                    job.worker_token_id = None
                    job.claimed_at = None
                    job.output_folder = None
                    job.output_name = None
                    job.output_size_bytes = None
                    job.retry_at = datetime.now(timezone.utc) + RETRY_DELAY
                    requeued = True
                else:
                    job.status = "failed"
                    job.error = message
                db.commit()
        finally:
            db.close()
        render_events.publish(job_id)
        return requeued

    def _requeue_job(self, job_id: int) -> None:
        db = SessionLocal()
        try:
            job = db.get(RenderJob, job_id)
            if job and job.status in {"dispatched", "rendering"}:
                job.status = "pending"
                job.worker_token_id = None
                job.claimed_at = None
                db.commit()
        finally:
            db.close()
        render_events.publish(job_id)


dispatcher = RenderDispatcher()
