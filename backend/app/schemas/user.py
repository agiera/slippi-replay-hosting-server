from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.schemas.user_management import RepositoryPublic


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    repositories: list[RepositoryPublic]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
