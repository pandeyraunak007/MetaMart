"""Permission inheritance and grant helpers. v1: grants only — no deny."""
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from metamart.auth import get_current_user
from metamart.db import get_db
from metamart.mart.models import (
    PERM_ADMIN,
    PERM_DELETE,
    PERM_MANAGE_PERMS,
    PERM_MANAGE_RULES,
    PERM_READ,
    PERM_WAIVE_FINDINGS,
    PERM_WRITE,
    M70Object,
    M70Permission,
    M70User,
    M70UserGroup,
)

MAX_DEPTH = 64


def ancestor_obj_ids(db: Session, obj_id: int) -> list[int]:
    """Return [obj_id, parent, grandparent, …] by walking m70_object.parent_obj_id."""
    ancestors: list[int] = []
    seen: set[int] = set()
    current: int | None = obj_id
    while current is not None and current not in seen and len(ancestors) < MAX_DEPTH:
        ancestors.append(current)
        seen.add(current)
        current = db.execute(
            select(M70Object.parent_obj_id).where(M70Object.obj_id == current)
        ).scalar_one_or_none()
    return ancestors


def user_group_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.execute(
            select(M70UserGroup.group_id).where(M70UserGroup.user_id == user_id)
        ).scalars()
    )


def effective_perms(db: Session, *, user_id: int, obj_id: int) -> int:
    """OR of all m70_permission grants for the user (and their groups) over
    obj_id and its ancestors. Returns 0 if no grants apply."""
    ancestors = ancestor_obj_ids(db, obj_id)
    if not ancestors:
        return 0

    groups = user_group_ids(db, user_id)
    user_clause = (M70Permission.grantee_type == "user") & (
        M70Permission.grantee_id == user_id
    )
    if groups:
        group_clause = (M70Permission.grantee_type == "group") & (
            M70Permission.grantee_id.in_(groups)
        )
        grantee_clause = user_clause | group_clause
    else:
        grantee_clause = user_clause

    stmt = select(M70Permission.perm_mask).where(
        M70Permission.obj_id.in_(ancestors),
        grantee_clause,
    )
    mask = 0
    for m in db.execute(stmt).scalars():
        mask |= m
    return mask


def require_permission(perm: int):
    """FastAPI dep factory. Path must contain `obj_id`."""

    def _check(
        obj_id: int,
        db: Session = Depends(get_db),
        user: M70User = Depends(get_current_user),
    ) -> M70User:
        mask = effective_perms(db, user_id=user.user_id, obj_id=obj_id)
        if (mask & perm) != perm:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Missing permission (need mask {perm}, have {mask})",
            )
        return user

    return _check


def grant(
    db: Session,
    *,
    grantee_id: int,
    grantee_type: str,
    obj_id: int,
    perm_mask: int,
    granted_by: int | None,
) -> M70Permission:
    """Upsert a grant: OR perm_mask into existing row if one exists, else insert."""
    existing = db.execute(
        select(M70Permission).where(
            M70Permission.grantee_id == grantee_id,
            M70Permission.grantee_type == grantee_type,
            M70Permission.obj_id == obj_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.perm_mask |= perm_mask
        db.flush()
        return existing
    row = M70Permission(
        grantee_id=grantee_id,
        grantee_type=grantee_type,
        obj_id=obj_id,
        perm_mask=perm_mask,
        granted_by=granted_by,
    )
    db.add(row)
    db.flush()
    return row


__all__ = [
    "PERM_READ",
    "PERM_WRITE",
    "PERM_DELETE",
    "PERM_ADMIN",
    "PERM_MANAGE_PERMS",
    "PERM_MANAGE_RULES",
    "PERM_WAIVE_FINDINGS",
    "ancestor_obj_ids",
    "user_group_ids",
    "effective_perms",
    "require_permission",
    "grant",
]
