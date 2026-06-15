from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RoleValue = Literal["user", "uploader", "superuser"]


class RepositoryPublic(BaseModel):
    id: int
    name: str
    is_public: bool

    model_config = {"from_attributes": True}


class ApiTokenPublic(BaseModel):
    id: int
    collection_name: str
    token_prefix: str
    repositories: list[RepositoryPublic]
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class ApiTokenCreateRequest(BaseModel):
    collection_name: str = Field(min_length=1, max_length=64)
    repository_ids: list[int] | None = None


class ApiTokenCreateResponse(BaseModel):
    token: str
    token_info: ApiTokenPublic


class UserRoleUpdateRequest(BaseModel):
    role: RoleValue


class RepositoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class UserRepositoriesUpdateRequest(BaseModel):
    repository_ids: list[int]
