"""Repository helpers over the M70_* tables."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from metamart.mart.models import (
    M70Folder,
    M70Library,
    M70Model,
    M70ModelVersion,
    M70Object,
    M70User,
)
from metamart.permissions import PERM_ADMIN, PERM_READ, PERM_WRITE, grant


# ─── Users ───────────────────────────────────────────────────

def create_user(
    db: Session, *, username: str, display_name: str, email: str | None
) -> M70User:
    u = M70User(username=username, display_name=display_name, email=email)
    db.add(u)
    db.flush()
    return u


def list_users(db: Session) -> list[M70User]:
    return list(db.execute(select(M70User).order_by(M70User.username)).scalars())


def get_user(db: Session, user_id: int) -> M70User | None:
    return db.get(M70User, user_id)


# ─── Libraries ───────────────────────────────────────────────

def create_library(
    db: Session,
    *,
    name: str,
    description: str | None,
    creator_user_id: int,
) -> M70Library:
    obj = M70Object(
        obj_type="LIBRARY",
        created_by=creator_user_id,
        modified_by=creator_user_id,
    )
    db.add(obj)
    db.flush()
    lib = M70Library(
        obj_id=obj.obj_id,
        name=name,
        description=description,
        owner_user_id=creator_user_id,
    )
    db.add(lib)
    db.flush()
    # Creator gets full perms on the new library (otherwise no one could administer it).
    grant(
        db,
        grantee_id=creator_user_id,
        grantee_type="user",
        obj_id=obj.obj_id,
        perm_mask=PERM_READ | PERM_WRITE | PERM_ADMIN,
        granted_by=creator_user_id,
    )
    return lib


def list_libraries(db: Session) -> list[M70Library]:
    stmt = (
        select(M70Library)
        .join(M70Object, M70Object.obj_id == M70Library.obj_id)
        .where(M70Object.is_deleted.is_(False))
        .order_by(M70Library.name)
    )
    return list(db.execute(stmt).scalars())


def get_library(db: Session, obj_id: int) -> M70Library | None:
    return db.get(M70Library, obj_id)


def list_library_root_folders(db: Session, library_obj_id: int) -> list[M70Folder]:
    stmt = select(M70Folder).where(
        M70Folder.library_obj_id == library_obj_id,
        M70Folder.parent_folder_obj_id.is_(None),
    )
    return list(db.execute(stmt).scalars())


# ─── Folders ─────────────────────────────────────────────────

def create_folder(
    db: Session,
    *,
    name: str,
    library_obj_id: int,
    parent_folder_obj_id: int | None,
    creator_user_id: int,
) -> M70Folder:
    # Hook parent_obj_id into m70_object so the permission walker can find it.
    parent_obj = parent_folder_obj_id if parent_folder_obj_id is not None else library_obj_id
    obj = M70Object(
        obj_type="FOLDER",
        parent_obj_id=parent_obj,
        created_by=creator_user_id,
        modified_by=creator_user_id,
    )
    db.add(obj)
    db.flush()
    folder = M70Folder(
        obj_id=obj.obj_id,
        name=name,
        library_obj_id=library_obj_id,
        parent_folder_obj_id=parent_folder_obj_id,
    )
    db.add(folder)
    db.flush()
    return folder


def get_folder(db: Session, obj_id: int) -> M70Folder | None:
    return db.get(M70Folder, obj_id)


def list_subfolders(db: Session, folder_obj_id: int) -> list[M70Folder]:
    return list(
        db.execute(
            select(M70Folder).where(M70Folder.parent_folder_obj_id == folder_obj_id)
        ).scalars()
    )


def list_folder_models(db: Session, folder_obj_id: int) -> list[M70Model]:
    return list(
        db.execute(
            select(M70Model).where(M70Model.folder_obj_id == folder_obj_id)
        ).scalars()
    )


# ─── Models ──────────────────────────────────────────────────

def create_model(
    db: Session,
    *,
    name: str,
    folder_obj_id: int,
    model_type: str,
    description: str | None,
    creator_user_id: int,
) -> M70Model:
    obj = M70Object(
        obj_type="MODEL",
        parent_obj_id=folder_obj_id,
        created_by=creator_user_id,
        modified_by=creator_user_id,
    )
    db.add(obj)
    db.flush()
    m = M70Model(
        obj_id=obj.obj_id,
        name=name,
        folder_obj_id=folder_obj_id,
        model_type=model_type,
        description=description,
    )
    db.add(m)
    db.flush()
    return m


def get_model(db: Session, obj_id: int) -> M70Model | None:
    return db.get(M70Model, obj_id)


def list_model_versions(db: Session, model_obj_id: int) -> list[M70ModelVersion]:
    return list(
        db.execute(
            select(M70ModelVersion)
            .where(M70ModelVersion.model_obj_id == model_obj_id)
            .order_by(M70ModelVersion.version_num.desc())
        ).scalars()
    )


def get_model_version(db: Session, version_id: int) -> M70ModelVersion | None:
    return db.get(M70ModelVersion, version_id)
