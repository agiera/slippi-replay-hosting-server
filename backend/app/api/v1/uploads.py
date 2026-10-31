import re
from pathlib import Path

from fastapi import APIRouter, Depends, File as UploadFileParam, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_active_api_token, get_api_token_user
from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.file import File
from app.models.user import User
from app.services.peppi_ingest import parse_slippi_bytes
from app.services.replay_upload import (
    DuplicateReplayError,
    compute_content_hash,
    persist_replay_upload,
    resolve_upload_repository,
)

router = APIRouter()

MAX_HASHES_PER_CHECK = 1000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _duplicate_response(exc: DuplicateReplayError) -> JSONResponse:
    # Flat body so clients can read the existing file's location directly.
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "Replay already uploaded",
            "id": exc.file_id,
            "folder": exc.folder,
            "name": exc.name,
            "size_bytes": exc.size_bytes,
        },
    )


@router.post("/files")
async def upload_replay_file(
    file: UploadFile = UploadFileParam(...),
    repository: str = Form(default="public"),
    x_content_sha256: str | None = Header(default=None, alias="X-Content-SHA256"),
    token_row: ApiToken = Depends(get_active_api_token),
    _: User = Depends(get_api_token_user),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

    original_name = Path(file.filename).name
    if not original_name.lower().endswith((".slp", ".zlp")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .slp and .zlp files are supported")

    data = await file.read()
    if x_content_sha256 is not None and x_content_sha256.strip().lower() != compute_content_hash(data):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Content-SHA256 does not match the uploaded bytes",
        )

    try:
        row = persist_replay_upload(
            db,
            token_row=token_row,
            repository_name=repository,
            original_name=original_name,
            data=data,
            parse_replay=parse_slippi_bytes,
        )
    except DuplicateReplayError as exc:
        return _duplicate_response(exc)

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


class ReplayHashCheckRequest(BaseModel):
    hashes: list[str] = Field(..., max_length=MAX_HASHES_PER_CHECK)

    @field_validator("hashes")
    @classmethod
    def _validate_hashes(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values]
        invalid = [value for value in normalized if not _SHA256_RE.match(value)]
        if invalid:
            raise ValueError("hashes must be 64-character hex SHA-256 digests")
        return normalized


@router.post("/files/check")
def check_replay_hashes(
    payload: ReplayHashCheckRequest,
    token_row: ApiToken = Depends(get_active_api_token),
    _: User = Depends(get_api_token_user),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, dict[str, str | int]]]:
    """Report which replay content hashes already exist in the token's repository.

    Lets upload clients skip sending bytes the server already has, and verify
    their local "already uploaded" records without listing every replay.
    """
    repository_row = resolve_upload_repository(db, token_row)
    hashes = sorted(set(payload.hashes))
    existing: dict[str, dict[str, str | int]] = {}
    if hashes:
        rows = db.scalars(
            select(File).where(File.repository_id == repository_row.id, File.sha256.in_(hashes))
        )
        for row in rows:
            existing[row.sha256] = {"id": row._id, "folder": row.folder, "name": row.name}
    return {"existing": existing}
