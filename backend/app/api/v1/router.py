from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.replays import router as replays_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(replays_router, prefix="/replays", tags=["replays"])
api_router.include_router(uploads_router, prefix="/uploads", tags=["uploads"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
