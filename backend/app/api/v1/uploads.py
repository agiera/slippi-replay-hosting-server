import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File as UploadFileParam, Form, Header, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import ClientDisconnect

from app.api.v1.deps import get_active_api_token, get_api_token_user
from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.file import File
from app.models.user import User
from app.services.peppi_ingest import parse_slippi_bytes
from app.services.replay_upload import persist_replay_upload
from app.services.slp_stream import finalize_streamed_slp

logger = logging.getLogger(__name__)

router = APIRouter()

# A live game is streamed byte-by-byte; if no data arrives for this long the game
# is treated as abandoned and whatever was received so far is finalized.
_STREAM_IDLE_TIMEOUT_S = 10 * 60
# Guards against an unbounded body; well above any real .slp game file.
_MAX_STREAM_BYTES = 250 * 1024 * 1024


@router.post("/files")
async def upload_replay_file(
    file: UploadFile = UploadFileParam(...),
    repository: str = Form(default="public"),
    token_row: ApiToken = Depends(get_active_api_token),
    _: User = Depends(get_api_token_user),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

    original_name = Path(file.filename).name
    if not original_name.lower().endswith((".slp", ".zlp")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .slp and .zlp files are supported")

    data = await file.read()
    row = persist_replay_upload(
        db,
        token_row=token_row,
        repository_name=repository,
        original_name=original_name,
        data=data,
        parse_replay=parse_slippi_bytes,
    )

    db.commit()

    saved = db.scalar(select(File).where(File._id == row._id))
    if not saved:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist file metadata")

    return {
        "id": saved._id,
        "folder": saved.folder,
        "name": saved.name,
        "size_bytes": saved.size_bytes,
    }


@router.post("/files/stream")
async def stream_replay_file(
    request: Request,
    x_filename: str = Header(..., alias="X-Filename"),
    x_repository: str = Header(default="public", alias="X-Repository"),
    token_row: ApiToken = Depends(get_active_api_token),
    _: User = Depends(get_api_token_user),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    """Accept a live console-mirror replay streamed as it is written.

    The client keeps the request body open, forwarding bytes as Slippi writes
    them, and closes it once the UBJSON container is closed (game finished) or
    after its own idle timeout. The server mirrors that with a 10-minute
    no-data timeout and, on a normal end, disconnect, or timeout, finalizes and
    persists whatever bytes were received.
    """
    original_name = Path(x_filename).name
    if not original_name.lower().endswith((".slp", ".zlp")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .slp and .zlp files are supported")

    # Release the pooled DB connection while the (potentially minutes-long)
    # stream runs; persist_replay_upload re-acquires one at finalize time.
    db.rollback()

    buffer = bytearray()
    body = request.stream()
    idle_timed_out = False
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(body.__anext__(), timeout=_STREAM_IDLE_TIMEOUT_S)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                idle_timed_out = True
                break
            if chunk:
                buffer.extend(chunk)
                if len(buffer) > _MAX_STREAM_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Replay stream exceeded the maximum allowed size",
                    )
    except ClientDisconnect:
        logger.info("Replay stream '%s' disconnected after %d bytes; finalizing", original_name, len(buffer))

    if not buffer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No replay data received")

    if idle_timed_out:
        logger.info("Replay stream '%s' idle-timed out after %d bytes; finalizing partial game", original_name, len(buffer))

    data = finalize_streamed_slp(bytes(buffer))
    row = persist_replay_upload(
        db,
        token_row=token_row,
        repository_name=x_repository,
        original_name=original_name,
        data=data,
        parse_replay=parse_slippi_bytes,
    )
    db.commit()

    saved = db.scalar(select(File).where(File._id == row._id))
    if not saved:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist file metadata")

    return {
        "id": saved._id,
        "folder": saved.folder,
        "name": saved.name,
        "size_bytes": saved.size_bytes,
    }
