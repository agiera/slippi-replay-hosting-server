from pathlib import Path

from fastapi import APIRouter, Depends, File as UploadFileParam, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_active_api_token, get_api_token_user
from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.file import File
from app.models.user import User
from app.services.peppi_ingest import parse_slippi_bytes
from app.services.replay_upload import persist_replay_upload

router = APIRouter()


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
