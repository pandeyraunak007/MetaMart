from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ─── Users ───────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=256)
    email: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    username: str
    display_name: str
    email: str | None
    is_active: bool


# ─── Libraries ───────────────────────────────────────────────

class LibraryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None


class LibraryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    obj_id: int
    name: str
    description: str | None
    owner_user_id: int | None


# ─── Folders ─────────────────────────────────────────────────

class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    library_obj_id: int
    parent_folder_obj_id: int | None = None


class FolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    obj_id: int
    name: str
    library_obj_id: int
    parent_folder_obj_id: int | None


class FolderChildren(BaseModel):
    folders: list[FolderRead]
    models: list["ModelRead"]


# ─── Models ──────────────────────────────────────────────────

class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    folder_obj_id: int
    model_type: str = Field(pattern="^(logical|physical|lp)$")
    description: str | None = None


class ModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    obj_id: int
    name: str
    folder_obj_id: int
    model_type: str
    description: str | None


FolderChildren.model_rebuild()


# ─── Versioning & locks ──────────────────────────────────────

class CheckinBody(BaseModel):
    comment: str | None = None
    is_named: bool = False
    named_label: str | None = None


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    version_id: int
    model_obj_id: int
    version_num: int
    author_user_id: int
    comment: str | None
    created_ts: datetime
    is_named: bool
    named_label: str | None


class LockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    obj_id: int
    locked_by_user_id: int
    locked_ts: datetime
    expires_ts: datetime | None


# ─── Permissions ─────────────────────────────────────────────

class PermissionGrant(BaseModel):
    grantee_id: int
    grantee_type: str = Field(pattern="^(user|group)$")
    obj_id: int
    perm_mask: int = Field(ge=0)


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    perm_id: int
    grantee_id: int
    grantee_type: str
    obj_id: int
    perm_mask: int
