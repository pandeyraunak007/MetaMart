"""Check-out / check-in flow for models.

M2 scope: lock acquisition, version-row creation, audit-log, lock release.
The workspace-diff application against specialization tables (m70_entity,
m70_attribute, …) using `temporal_upsert` lands in M2.5 when those tables exist.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from metamart.audit import audit
from metamart.mart.models import M70Lock, M70Model, M70ModelVersion

LOCK_TTL_SECONDS = 4 * 60 * 60  # 4h default check-out lifetime


def checkout(db: Session, *, model_obj_id: int, user_id: int) -> M70Lock:
    """Acquire (or refresh) a lock on a model.

    - Same user re-checking out: refreshes the expiry.
    - Different user, expired lock: takes over.
    - Different user, live lock: 409.
    """
    model = db.get(M70Model, model_obj_id)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")

    now = datetime.now(timezone.utc)
    existing = db.get(M70Lock, model_obj_id)
    if existing is not None:
        same_user = existing.locked_by_user_id == user_id
        expired = existing.expires_ts is not None and existing.expires_ts < now
        if same_user or expired:
            existing.locked_by_user_id = user_id
            existing.locked_ts = now
            existing.expires_ts = now + timedelta(seconds=LOCK_TTL_SECONDS)
            db.flush()
            audit(
                db,
                action="model.checkout.refresh",
                actor_user_id=user_id,
                obj_id=model_obj_id,
            )
            return existing
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Model is locked by user {existing.locked_by_user_id} until {existing.expires_ts}",
        )

    lock = M70Lock(
        obj_id=model_obj_id,
        locked_by_user_id=user_id,
        locked_ts=now,
        expires_ts=now + timedelta(seconds=LOCK_TTL_SECONDS),
    )
    db.add(lock)
    db.flush()
    audit(db, action="model.checkout", actor_user_id=user_id, obj_id=model_obj_id)
    return lock


def checkin(
    db: Session,
    *,
    model_obj_id: int,
    user_id: int,
    comment: str | None,
    is_named: bool = False,
    named_label: str | None = None,
) -> M70ModelVersion:
    """Commit and create a new model_version. Caller must hold the lock."""
    model = db.get(M70Model, model_obj_id)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")

    lock = db.get(M70Lock, model_obj_id)
    if lock is None or lock.locked_by_user_id != user_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You must hold the lock on this model to check in",
        )

    last_num = db.execute(
        select(M70ModelVersion.version_num)
        .where(M70ModelVersion.model_obj_id == model_obj_id)
        .order_by(M70ModelVersion.version_num.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_num = (last_num or 0) + 1

    version = M70ModelVersion(
        model_obj_id=model_obj_id,
        version_num=next_num,
        author_user_id=user_id,
        comment=comment,
        is_named=is_named,
        named_label=named_label,
    )
    db.add(version)
    db.flush()

    # M2.5: apply workspace diff to specialization tables via temporal_upsert here.

    audit(
        db,
        action="model.checkin",
        actor_user_id=user_id,
        obj_id=model_obj_id,
        details={
            "version_id": version.version_id,
            "version_num": next_num,
            "comment": comment,
        },
    )

    db.delete(lock)
    db.flush()
    return version


def release_lock(db: Session, *, model_obj_id: int, user_id: int) -> bool:
    """Explicit check-in-less unlock. Returns True if released, False if not held by user."""
    lock = db.get(M70Lock, model_obj_id)
    if lock is None:
        return False
    if lock.locked_by_user_id != user_id:
        return False
    db.delete(lock)
    db.flush()
    audit(db, action="model.checkout.release", actor_user_id=user_id, obj_id=model_obj_id)
    return True
