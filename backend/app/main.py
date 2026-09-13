from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.ftp_server import start_ftp_server, stop_ftp_server
from app.services.user_service import ensure_superuser_exists


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db = SessionLocal()
    try:
        ensure_superuser_exists(db)
    finally:
        db.close()

    start_ftp_server()
    try:
        yield
    finally:
        stop_ftp_server()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
