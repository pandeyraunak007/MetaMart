"""SCD Type 2 helpers for versioned mart tables.

Convention: [version_from, version_to) — half-open interval.
- version_from: first version the row is valid in
- version_to:   first version the row is NOT valid in (NULL = currently live)

"State at version V":  WHERE version_from <= V AND (version_to IS NULL OR version_to > V)
"""
from typing import Any

from sqlalchemy import and_, update
from sqlalchemy.orm import Session


def temporal_upsert(
    db: Session,
    model_class: Any,
    *,
    obj_id: int,
    new_version_id: int,
    fields: dict[str, Any],
    extra_keys: dict[str, Any] | None = None,
) -> Any:
    """Close the currently-live row(s) for this identity, then insert a new live row.

    model_class must define `obj_id`, `version_from`, and `version_to` columns.
    extra_keys lets composite identities (e.g. m70_property's (obj_id, prop_id)) be specified.
    Returns the newly-inserted row.
    """
    conditions = [model_class.obj_id == obj_id, model_class.version_to.is_(None)]
    if extra_keys:
        for col, val in extra_keys.items():
            conditions.append(getattr(model_class, col) == val)

    db.execute(
        update(model_class).where(and_(*conditions)).values(version_to=new_version_id)
    )

    new_row = model_class(
        obj_id=obj_id,
        version_from=new_version_id,
        version_to=None,
        **(extra_keys or {}),
        **fields,
    )
    db.add(new_row)
    db.flush()
    return new_row


def temporal_delete(
    db: Session,
    model_class: Any,
    *,
    obj_id: int,
    new_version_id: int,
    extra_keys: dict[str, Any] | None = None,
) -> int:
    """Close currently-live row(s) without inserting a replacement.

    Returns the number of rows closed.
    """
    conditions = [model_class.obj_id == obj_id, model_class.version_to.is_(None)]
    if extra_keys:
        for col, val in extra_keys.items():
            conditions.append(getattr(model_class, col) == val)

    result = db.execute(
        update(model_class).where(and_(*conditions)).values(version_to=new_version_id)
    )
    db.flush()
    return result.rowcount or 0
