from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from metamart.audit import audit
from metamart.auth import get_current_user
from metamart.db import get_db
from metamart.mart import repo, schemas
from metamart.mart.models import M70User
from metamart.mart.versioning import checkin, checkout, release_lock
from metamart.permissions import (
    PERM_ADMIN,
    PERM_MANAGE_PERMS,
    PERM_READ,
    PERM_WRITE,
    effective_perms,
    grant,
    require_permission,
)

router = APIRouter(prefix="/mart", tags=["mart"])


# ─── Users (bootstrap; replaced by real auth in M6) ──────────

@router.post(
    "/users",
    response_model=schemas.UserRead,
    status_code=status.HTTP_201_CREATED,
)
def api_create_user(body: schemas.UserCreate, db: Session = Depends(get_db)):
    u = repo.create_user(db, **body.model_dump())
    db.commit()
    db.refresh(u)
    return u


@router.get("/users", response_model=list[schemas.UserRead])
def api_list_users(db: Session = Depends(get_db)):
    return repo.list_users(db)


# ─── Libraries ───────────────────────────────────────────────

@router.get("/libraries", response_model=list[schemas.LibraryRead])
def api_list_libraries(
    db: Session = Depends(get_db),
    user: M70User = Depends(get_current_user),
):
    return repo.list_libraries(db)


@router.post(
    "/libraries",
    response_model=schemas.LibraryRead,
    status_code=status.HTTP_201_CREATED,
)
def api_create_library(
    body: schemas.LibraryCreate,
    db: Session = Depends(get_db),
    user: M70User = Depends(get_current_user),
):
    lib = repo.create_library(
        db,
        name=body.name,
        description=body.description,
        creator_user_id=user.user_id,
    )
    audit(
        db,
        action="library.create",
        actor_user_id=user.user_id,
        obj_id=lib.obj_id,
        details={"name": body.name},
    )
    db.commit()
    db.refresh(lib)
    return lib


@router.get(
    "/libraries/{obj_id}",
    response_model=schemas.LibraryRead,
    dependencies=[Depends(require_permission(PERM_READ))],
)
def api_get_library(obj_id: int, db: Session = Depends(get_db)):
    lib = repo.get_library(db, obj_id)
    if not lib:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Library not found")
    return lib


@router.get(
    "/libraries/{obj_id}/folders",
    response_model=list[schemas.FolderRead],
    dependencies=[Depends(require_permission(PERM_READ))],
)
def api_list_library_root_folders(obj_id: int, db: Session = Depends(get_db)):
    return repo.list_library_root_folders(db, obj_id)


# ─── Folders ─────────────────────────────────────────────────

@router.post(
    "/folders",
    response_model=schemas.FolderRead,
    status_code=status.HTTP_201_CREATED,
)
def api_create_folder(
    body: schemas.FolderCreate,
    db: Session = Depends(get_db),
    user: M70User = Depends(get_current_user),
):
    parent_obj_id = body.parent_folder_obj_id or body.library_obj_id
    mask = effective_perms(db, user_id=user.user_id, obj_id=parent_obj_id)
    if (mask & PERM_WRITE) != PERM_WRITE:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Need WRITE on parent folder/library"
        )

    folder = repo.create_folder(
        db,
        name=body.name,
        library_obj_id=body.library_obj_id,
        parent_folder_obj_id=body.parent_folder_obj_id,
        creator_user_id=user.user_id,
    )
    audit(
        db,
        action="folder.create",
        actor_user_id=user.user_id,
        obj_id=folder.obj_id,
        details={"name": body.name},
    )
    db.commit()
    db.refresh(folder)
    return folder


@router.get(
    "/folders/{obj_id}",
    response_model=schemas.FolderRead,
    dependencies=[Depends(require_permission(PERM_READ))],
)
def api_get_folder(obj_id: int, db: Session = Depends(get_db)):
    folder = repo.get_folder(db, obj_id)
    if not folder:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")
    return folder


@router.get(
    "/folders/{obj_id}/children",
    response_model=schemas.FolderChildren,
    dependencies=[Depends(require_permission(PERM_READ))],
)
def api_folder_children(obj_id: int, db: Session = Depends(get_db)):
    return schemas.FolderChildren(
        folders=repo.list_subfolders(db, obj_id),
        models=repo.list_folder_models(db, obj_id),
    )


# ─── Models ──────────────────────────────────────────────────

@router.post(
    "/models",
    response_model=schemas.ModelRead,
    status_code=status.HTTP_201_CREATED,
)
def api_create_model(
    body: schemas.ModelCreate,
    db: Session = Depends(get_db),
    user: M70User = Depends(get_current_user),
):
    mask = effective_perms(db, user_id=user.user_id, obj_id=body.folder_obj_id)
    if (mask & PERM_WRITE) != PERM_WRITE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Need WRITE on parent folder")

    m = repo.create_model(
        db,
        name=body.name,
        folder_obj_id=body.folder_obj_id,
        model_type=body.model_type,
        description=body.description,
        creator_user_id=user.user_id,
    )
    audit(
        db,
        action="model.create",
        actor_user_id=user.user_id,
        obj_id=m.obj_id,
        details={"name": body.name, "model_type": body.model_type},
    )
    db.commit()
    db.refresh(m)
    return m


@router.get(
    "/models/{obj_id}",
    response_model=schemas.ModelRead,
    dependencies=[Depends(require_permission(PERM_READ))],
)
def api_get_model(obj_id: int, db: Session = Depends(get_db)):
    m = repo.get_model(db, obj_id)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    return m


# ─── Check-out / check-in / versions ─────────────────────────

@router.post(
    "/models/{obj_id}/checkout",
    response_model=schemas.LockRead,
    dependencies=[Depends(require_permission(PERM_WRITE))],
)
def api_checkout(
    obj_id: int,
    db: Session = Depends(get_db),
    user: M70User = Depends(get_current_user),
):
    lock = checkout(db, model_obj_id=obj_id, user_id=user.user_id)
    db.commit()
    db.refresh(lock)
    return lock


@router.post(
    "/models/{obj_id}/checkin",
    response_model=schemas.VersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PERM_WRITE))],
)
def api_checkin(
    obj_id: int,
    body: schemas.CheckinBody,
    db: Session = Depends(get_db),
    user: M70User = Depends(get_current_user),
):
    version = checkin(
        db,
        model_obj_id=obj_id,
        user_id=user.user_id,
        comment=body.comment,
        is_named=body.is_named,
        named_label=body.named_label,
    )
    db.commit()
    db.refresh(version)
    return version


@router.delete(
    "/models/{obj_id}/checkout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission(PERM_WRITE))],
)
def api_release_lock(
    obj_id: int,
    db: Session = Depends(get_db),
    user: M70User = Depends(get_current_user),
):
    released = release_lock(db, model_obj_id=obj_id, user_id=user.user_id)
    if not released:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No lock held by you on this model"
        )
    db.commit()
    return None


@router.get(
    "/models/{obj_id}/versions",
    response_model=list[schemas.VersionRead],
    dependencies=[Depends(require_permission(PERM_READ))],
)
def api_list_versions(obj_id: int, db: Session = Depends(get_db)):
    return repo.list_model_versions(db, obj_id)


# ─── Permissions admin ───────────────────────────────────────

@router.post(
    "/permissions",
    response_model=schemas.PermissionRead,
    status_code=status.HTTP_201_CREATED,
)
def api_grant_permission(
    body: schemas.PermissionGrant,
    db: Session = Depends(get_db),
    user: M70User = Depends(get_current_user),
):
    mask = effective_perms(db, user_id=user.user_id, obj_id=body.obj_id)
    required = PERM_MANAGE_PERMS | PERM_ADMIN
    if (mask & required) == 0:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Need MANAGE_PERMS or ADMIN to grant permissions"
        )

    p = grant(
        db,
        grantee_id=body.grantee_id,
        grantee_type=body.grantee_type,
        obj_id=body.obj_id,
        perm_mask=body.perm_mask,
        granted_by=user.user_id,
    )
    audit(
        db,
        action="permission.grant",
        actor_user_id=user.user_id,
        obj_id=body.obj_id,
        details={
            "grantee_id": body.grantee_id,
            "grantee_type": body.grantee_type,
            "perm_mask": body.perm_mask,
        },
    )
    db.commit()
    db.refresh(p)
    return p
