"""Append rows to m70_audit_log. Caller commits."""
from typing import Any

from sqlalchemy.orm import Session

from metamart.mart.models import M70AuditLog


def audit(
    db: Session,
    *,
    action: str,
    actor_user_id: int | None,
    obj_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        M70AuditLog(
            obj_id=obj_id,
            action=action,
            actor_user_id=actor_user_id,
            details=details,
        )
    )
    db.flush()
