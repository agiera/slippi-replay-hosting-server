from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


RoleValue = Literal["user", "uploader", "superuser"]


class RepositoryPublic(BaseModel):
    id: int
    name: str
    is_public: bool

    model_config = {"from_attributes": True}


class ApiTokenPublic(BaseModel):
    id: int
    source_name: str
    collection_name: str | None = None
    token_prefix: str
    repositories: list[RepositoryPublic]
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True, "populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_source_name(cls, data):
        if isinstance(data, dict) and "source_name" not in data and data.get("collection_name"):
            data = {**data, "source_name": data["collection_name"]}
        return data

    @model_validator(mode="after")
    def ensure_legacy_collection_name(self) -> "ApiTokenPublic":
        if not self.collection_name:
            self.collection_name = self.source_name
        return self


class ApiTokenCreateRequest(BaseModel):
    source_name: str = Field(min_length=1, max_length=64)
    repository_ids: list[int] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_source_name(cls, data):
        if isinstance(data, dict) and "source_name" not in data and data.get("collection_name"):
            data = {**data, "source_name": data["collection_name"]}
        return data

    @model_validator(mode="after")
    def enforce_single_repository(self) -> "ApiTokenCreateRequest":
        if self.repository_ids and len(self.repository_ids) > 1:
            raise ValueError("A source can only belong to one repository")
        return self


class ApiTokenCreateResponse(BaseModel):
    token: str
    token_info: ApiTokenPublic


class UserRoleUpdateRequest(BaseModel):
    role: RoleValue


class RepositoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class UserRepositoriesUpdateRequest(BaseModel):
    repository_ids: list[int]
