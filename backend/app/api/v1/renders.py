import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_active_api_token, get_api_token_user, get_current_user, get_optional_user
from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.models.api_token import ApiToken
from app.models.file import File
from app.models.render_job import RenderJob
from app.models.repository import Repository
from app.models.user import User
from app.schemas.render import CreateRenderJobRequest, RenderJobPublic
from app.services.render_dispatch import DEFAULT_MAX_CONCURRENT, MAX_RENDER_ATTEMPTS, RETRY_DELAY, dispatcher
from app.services.render_events import render_events
from app.services.render_output import new_expiry, prune_expired_outputs, refresh_expiry

logger = logging.getLogger(__name__)

router = APIRouter()

_ACTIVE_STATUSES = {"pending", "dispatched", "rendering"}
_TERMINAL_STATUSES = {"completed", "failed", "expired"}


def _to_public(job: RenderJob) -> RenderJobPublic:
    return RenderJobPublic(
        id=job.id,
        file_id=job.file_id,
        status=job.status,
        error=job.error,
        output_size_bytes=job.output_size_bytes,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        expires_at=job.expires_at,
        has_output=bool(job.output_name),
    )


def _is_playable(job: RenderJob) -> bool:
    if job.status != "completed" or not job.output_name:
        return False
    if job.expires_at is not None and job.expires_at < datetime.now(timezone.utc):
        return False
    return True


def _repository_name_from_folder(folder: str | None) -> str | None:
    if not folder:
        return None
    parts = [part for part in folder.split("/") if part]
    if not parts:
        return None
    if parts[0] == "uploads":
        return parts[1] if len(parts) > 1 else None
    return parts[0]


def _user_can_access_file(db: Session, user: User, file_row: File) -> bool:
    if user.role == "superuser":
        return True
    repo_name = _repository_name_from_folder(file_row.folder)
    if not repo_name:
        return False
    repo = db.scalar(select(Repository).where(Repository.name == repo_name))
    if not repo:
        return False
    if repo.is_public:
        return True
    return any(repo.id == owned.id for owned in user.repositories)


def _file_repo_is_public(db: Session, file_row: File) -> bool:
    repo_name = _repository_name_from_folder(file_row.folder)
    if not repo_name:
        return False
    repo = db.scalar(select(Repository).where(Repository.name == repo_name))
    return bool(repo and repo.is_public)


def _resolve_worker_token(db: Session, token_value: str | None) -> ApiToken | None:
    if not token_value:
        return None

    token_hash = hashlib.sha256(token_value.encode("utf-8")).hexdigest()
    token_row = db.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash))
    if not token_row or token_row.revoked_at is not None:
        return None

    user = db.get(User, token_row.user_id)
    if not user or user.role not in {"uploader", "superuser"}:
        return None

    return token_row


@router.post("/jobs", response_model=RenderJobPublic)
async def create_render_job(
    payload: CreateRenderJobRequest,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> RenderJobPublic:
    prune_expired_outputs(db)

    file_row = db.get(File, payload.file_id)
    if not file_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if current_user is not None:
        if not _user_can_access_file(db, current_user, file_row):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this repository")
    elif not _file_repo_is_public(db, file_row):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required to render this replay")

    latest = db.scalar(
        select(RenderJob)
        .where(RenderJob.file_id == payload.file_id)
        .order_by(RenderJob.created_at.desc())
    )
    # An in-flight or still-valid rendered VOD is reused instead of re-rendering.
    if latest and (latest.status in _ACTIVE_STATUSES or _is_playable(latest)):
        return _to_public(latest)

    job = RenderJob(
        file_id=payload.file_id,
        status="pending",
        requested_by_user_id=current_user.id if current_user else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    await dispatcher.dispatch_pending()
    return _to_public(job)


@router.get("/jobs/by-file/{file_id}", response_model=RenderJobPublic | None)
def get_render_job_for_file(
    file_id: int,
    db: Session = Depends(get_db),
) -> RenderJobPublic | None:
    prune_expired_outputs(db)
    job = db.scalar(
        select(RenderJob).where(RenderJob.file_id == file_id).order_by(RenderJob.created_at.desc())
    )
    if not job:
        return None
    return _to_public(job)


@router.get("/jobs", response_model=list[RenderJobPublic])
def list_render_jobs(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RenderJobPublic]:
    prune_expired_outputs(db)
    jobs = db.scalars(select(RenderJob).order_by(RenderJob.created_at.desc()).limit(limit)).all()
    return [_to_public(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=RenderJobPublic)
def get_render_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> RenderJobPublic:
    job = db.get(RenderJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found")
    return _to_public(job)


def _sse_frame(job: RenderJob) -> str:
    payload = _to_public(job).model_dump(mode="json")
    return f"event: render_job\ndata: {json.dumps(payload)}\n\n"


@router.get("/jobs/{job_id}/events")
async def render_job_events(job_id: int, request: Request) -> StreamingResponse:
    db = SessionLocal()
    try:
        job = db.get(RenderJob, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found")
        initial_frame = _sse_frame(job)
        initial_terminal = job.status in _TERMINAL_STATUSES
    finally:
        db.close()

    async def event_stream():
        queue = render_events.subscribe(job_id)
        try:
            yield initial_frame
            if initial_terminal:
                return
            while True:
                if await request.is_disconnected():
                    return
                try:
                    await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                inner = SessionLocal()
                try:
                    job = inner.get(RenderJob, job_id)
                    if not job:
                        return
                    yield _sse_frame(job)
                    if job.status in _TERMINAL_STATUSES:
                        return
                finally:
                    inner.close()
        finally:
            render_events.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/jobs/{job_id}/result", response_model=RenderJobPublic)
async def submit_render_result(
    job_id: int,
    request: Request,
    token_row: ApiToken = Depends(get_active_api_token),
    _: User = Depends(get_api_token_user),
    db: Session = Depends(get_db),
) -> RenderJobPublic:
    job = db.get(RenderJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found")
    if job.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Render job already completed")

    file_row = db.get(File, job.file_id)
    folder = file_row.folder if file_row else "renders"
    stem = Path(file_row.name).stem if file_row else f"render-{job_id}"
    output_name = f"{stem}.mp4"

    storage_root = Path(settings.RENDER_STORAGE_DIR).resolve()
    target_dir = (storage_root / folder).resolve()
    if storage_root != target_dir and storage_root not in target_dir.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid output path")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / output_name

    # Publish the output location up front so the UI can begin progressive
    # playback of the fragmented mp4 while the worker is still streaming it.
    job.status = "rendering"
    job.error = None
    job.worker_token_id = token_row.id
    job.output_folder = folder
    job.output_name = output_name
    job.output_size_bytes = 0
    if job.claimed_at is None:
        job.claimed_at = datetime.now(timezone.utc)
    db.commit()
    render_events.publish(job_id)

    total = 0
    # TEMP DIAGNOSTIC LOGGING (remove after debugging the mid-stream upload stall).
    import time as _time
    _t0 = _time.monotonic()
    _last_log = _t0
    _last_total = 0
    _chunks = 0
    logger.warning("UPLOAD-DIAG job=%s START receiving result body", job_id)
    try:
        with target_path.open("wb") as fh:
            async for chunk in request.stream():
                if not chunk:
                    continue
                # Offload the disk write so the event loop keeps draining the
                # upload socket; a blocking write here back-pressures the worker's
                # ffmpeg pipe and freezes the live encode.
                _w0 = _time.monotonic()
                await asyncio.to_thread(fh.write, chunk)
                _w1 = _time.monotonic()
                total += len(chunk)
                _chunks += 1
                if _w1 - _last_log >= 1.0:
                    rate = (total - _last_total) / (_w1 - _last_log) / 1024.0
                    logger.warning(
                        "UPLOAD-DIAG job=%s total=%.1fMB chunks=%d rate=%.0fKB/s lastwrite=%.1fms",
                        job_id, total / 1048576.0, _chunks, rate, (_w1 - _w0) * 1000.0,
                    )
                    _last_log = _w1
                    _last_total = total
        logger.warning(
            "UPLOAD-DIAG job=%s STREAM ENDED total=%.1fMB chunks=%d elapsed=%.1fs",
            job_id, total / 1048576.0, _chunks, _time.monotonic() - _t0,
        )
    except Exception:
        logger.exception(
            "UPLOAD-DIAG job=%s STREAM RAISED after total=%.1fMB chunks=%d elapsed=%.1fs",
            job_id, total / 1048576.0, _chunks, _time.monotonic() - _t0,
        )
        # A dropped/aborted stream leaves the job to be retried after a timeout,
        # or fails it once attempts are exhausted.
        if job.attempts < MAX_RENDER_ATTEMPTS:
            job.status = "pending"
            job.error = "render upload interrupted"
            job.worker_token_id = None
            job.claimed_at = None
            job.output_folder = None
            job.output_name = None
            job.output_size_bytes = None
            job.retry_at = datetime.now(timezone.utc) + RETRY_DELAY
        else:
            job.status = "failed"
            job.error = "render upload interrupted"
        db.commit()
        render_events.publish(job_id)
        await dispatcher.on_job_finished(job_id)
        raise

    # The daemon only ends this stream cleanly after the render finished and the
    # complete mp4 drained to EOF; an interrupted worker instead trips
    # ClientDisconnect above (handled as failed), so a clean end means the file is
    # whole and can be published as completed.
    job.status = "completed"
    job.error = None
    job.output_size_bytes = total
    job.completed_at = datetime.now(timezone.utc)
    job.expires_at = new_expiry()
    db.commit()
    db.refresh(job)

    render_events.publish(job_id)
    await dispatcher.on_job_finished(job_id)
    return _to_public(job)


@router.get("/jobs/{job_id}/download")
async def download_render_output(job_id: int, request: Request, db: Session = Depends(get_db)):
    prune_expired_outputs(db)
    job = db.get(RenderJob, job_id)
    if not job or not job.output_name or not job.output_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rendered video is not available")

    storage_root = Path(settings.RENDER_STORAGE_DIR).resolve()
    candidate = (storage_root / job.output_folder / job.output_name).resolve()
    if storage_root != candidate and storage_root not in candidate.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rendered video is missing from storage")

    if job.status == "completed":
        # Viewing a finished VOD slides its expiry window forward.
        refresh_expiry(db, job)
        return FileResponse(
            path=candidate,
            filename=job.output_name,
            media_type="video/mp4",
            content_disposition_type="inline",
        )

    # In-progress render: tail the growing fragmented mp4 until the job finishes
    # so viewers can start watching before the render/upload completes.
    async def tail_growing_file():
        with candidate.open("rb") as fh:
            while True:
                chunk = fh.read(65536)
                if chunk:
                    yield chunk
                    continue
                if await request.is_disconnected():
                    return
                inner = SessionLocal()
                try:
                    current = inner.get(RenderJob, job_id)
                    status_now = current.status if current else "failed"
                finally:
                    inner.close()
                if status_now in _TERMINAL_STATUSES:
                    final = fh.read()
                    if final:
                        yield final
                    return
                await asyncio.sleep(0.25)

    return StreamingResponse(
        tail_growing_file(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'inline; filename="{job.output_name}"',
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@router.websocket("/ws")
async def render_worker_ws(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    max_concurrent: int | None = Query(default=None),
) -> None:
    header_token = websocket.headers.get("x-api-token")
    if not token and header_token:
        token = header_token

    db = SessionLocal()
    try:
        token_row = _resolve_worker_token(db, token)
        token_id = token_row.id if token_row else None
        source_name = token_row.source_name if token_row else ""
    finally:
        db.close()

    if token_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    conn = await dispatcher.register(
        websocket,
        token_id,
        source_name,
        max_concurrent if max_concurrent is not None else DEFAULT_MAX_CONCURRENT,
    )
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = _decode_message(raw)
            except ValueError:
                continue
            await dispatcher.handle_worker_message(conn, message)
    except WebSocketDisconnect:
        pass
    finally:
        await dispatcher.unregister(conn)


def _decode_message(raw: str) -> dict:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("message must be an object")
    return parsed
