"""Normalize various JSON catalog shapes into MetaMart's native format.

Handles:
- Native MetaMart shape (passthrough): `{name, model_type, entities: [...]}`
- erwin Data Modeler exports (PascalCase keys, `Entities`/`Attributes`)
- Generic SQL-ish dumps: `{tables: [{name, columns: [...]}]}`

Any shape not detected here passes through unchanged — `catalog_from_json`
will then raise its own informative error.
"""
from __future__ import annotations

from typing import Any


def normalize_catalog(data: Any) -> Any:
    """Convert known foreign shapes to native catalog format. Idempotent."""
    if not isinstance(data, dict):
        return data
    # Already native
    if "entities" in data and isinstance(data["entities"], list):
        return data
    if _looks_like_erwin(data):
        return _adapt_erwin(data)
    if "tables" in data and isinstance(data["tables"], list):
        return _adapt_tables(data)
    return data


# ── helpers ──────────────────────────────────────────────────

def _g(d: Any, *keys: str, default: Any = None) -> Any:
    """Pick the first non-None value among the given keys (case variations).

    Useful for normalizing PascalCase / camelCase / snake_case field names
    found in different JSON exports.
    """
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _slug(name: str | None) -> str:
    if not name:
        return "unknown"
    return (
        str(name)
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def _entity_id_from_ref(ref: Any) -> str:
    if isinstance(ref, dict):
        name = _g(ref, "Name", "name", "EntityName", "entityName", "PhysicalName")
        return f"e_{_slug(name)}"
    return f"e_{_slug(str(ref))}"


# ── erwin adapter ────────────────────────────────────────────

def _looks_like_erwin(data: dict) -> bool:
    indicators = ["Entities", "ERwinModel", "erwinModel", "DataModel", "Entity"]
    return any(k in data for k in indicators)


def _adapt_erwin(data: dict) -> dict[str, Any]:
    """erwin DM JSON → native catalog. Tolerates several common key variations."""
    model_block = _g(data, "Model", "ERwinModel", "erwinModel", "DataModel", default={})
    model_name = (
        _g(data, "Name", "ModelName", "name", "modelName")
        or _g(model_block, "Name", "ModelName", "name", "modelName")
    )

    raw_entities = (
        _g(data, "Entities", "Tables", "entities", "tables", "Entity")
        or _g(
            model_block,
            "Entity",
            "Entities",
            "Table",
            "Tables",
            "entity",
            "entities",
            default=[],
        )
    )
    if not isinstance(raw_entities, list):
        raw_entities = []

    entities = [_adapt_erwin_entity(e, i) for i, e in enumerate(raw_entities) if isinstance(e, dict)]

    raw_rels = (
        _g(data, "Relationships", "relationships")
        or _g(model_block, "Relationship", "Relationships", "relationship", "relationships", default=[])
    )
    if not isinstance(raw_rels, list):
        raw_rels = []

    relationships: list[dict[str, Any]] = []
    for i, r in enumerate(raw_rels):
        if not isinstance(r, dict):
            continue
        parent_ref = _g(r, "ParentEntity", "FromEntity", "Parent", "parent", "From", "from")
        child_ref = _g(r, "ChildEntity", "ToEntity", "Child", "child", "To", "to")
        if not parent_ref or not child_ref:
            continue
        relationships.append(
            {
                "id": f"r{i}",
                "name": _g(r, "Name", "name"),
                "parent": _entity_id_from_ref(parent_ref),
                "child": _entity_id_from_ref(child_ref),
                "cardinality": _g(r, "Cardinality", "cardinality", default="one_to_many"),
                "is_identifying": bool(_g(r, "IsIdentifying", "isIdentifying", default=False)),
            }
        )

    return {
        "name": model_name or "Untitled (erwin import)",
        "model_type": "physical",
        "entities": entities,
        "relationships": relationships,
    }


def _adapt_erwin_entity(e: dict, idx: int) -> dict[str, Any]:
    logical = _g(
        e,
        "LogicalName",
        "logicalName",
        "Name",
        "name",
        "EntityName",
        "entityName",
        default=f"Entity{idx}",
    )
    physical = _g(
        e,
        "PhysicalName",
        "physicalName",
        "TableName",
        "tableName",
        "Name",
        "name",
        default=logical,
    )
    e_id = f"e_{_slug(physical or logical)}_{idx}"

    raw_attrs = _g(
        e, "Attributes", "Columns", "attributes", "columns", "Attribute", "Column", default=[]
    )
    if not isinstance(raw_attrs, list):
        raw_attrs = []

    attributes: list[dict[str, Any]] = []
    pk_attr_ids: list[str] = []
    pk_attr_names: list[str] = []  # parallel: physical names for matching against explicit Keys block

    for j, a in enumerate(raw_attrs):
        if not isinstance(a, dict):
            continue
        a_logical = _g(
            a,
            "LogicalName",
            "logicalName",
            "Name",
            "name",
            "AttributeName",
            "attributeName",
            default=f"attr_{j}",
        )
        a_physical = _g(
            a,
            "PhysicalName",
            "physicalName",
            "ColumnName",
            "columnName",
            "Name",
            "name",
            default=a_logical,
        )
        a_type = _g(
            a,
            "DataType",
            "dataType",
            "Type",
            "type",
            "Datatype",
            "datatype",
            "PhysicalDataType",
            default="VARCHAR(255)",
        )

        # Nullability: try positive (NotNull/Required) and negative (Nullable=false) flags.
        is_nullable = True
        not_null_flag = _g(a, "NotNull", "notNull", "IsNotNull", "isNotNull", "Required", "required")
        if not_null_flag is True:
            is_nullable = False
        nullable_flag = _g(a, "Nullable", "nullable", "IsNullable", "isNullable")
        if nullable_flag is False:
            is_nullable = False

        a_id = f"{e_id}_a{j}"
        attributes.append(
            {
                "id": a_id,
                "logical_name": str(a_logical),
                "physical_name": str(a_physical),
                "data_type": str(a_type),
                "is_nullable": is_nullable,
                "position": j + 1,
            }
        )

        is_pk = (
            _g(a, "IsPK", "isPK", "isPk", "IsPrimaryKey", "primary_key", "primaryKey", "PrimaryKey")
            or str(_g(a, "Key", default="")).upper() == "PK"
        )
        if is_pk:
            pk_attr_ids.append(a_id)
            pk_attr_names.append(str(a_physical))

    keys: list[dict[str, Any]] = []
    if pk_attr_ids:
        keys.append(
            {
                "id": f"{e_id}_pk",
                "name": f"pk_{physical}",
                "key_type": "PK",
                "members": pk_attr_ids,
            }
        )

    # Also handle an explicit Keys block (erwin sometimes records PKs there only).
    raw_keys = _g(e, "Keys", "keys", default=[])
    if not isinstance(raw_keys, list):
        raw_keys = []
    for k_idx, k in enumerate(raw_keys):
        if not isinstance(k, dict):
            continue
        k_type = str(_g(k, "Type", "type", "KeyType", "keyType", default="PK")).upper()
        if k_type not in ("PK", "AK", "IE"):
            continue
        if k_type == "PK" and pk_attr_ids:
            continue  # already captured above
        member_refs = _g(k, "Members", "members", "Attributes", "attributes", default=[])
        if not isinstance(member_refs, list):
            continue
        member_ids: list[str] = []
        for mref in member_refs:
            if isinstance(mref, dict):
                mref_name = _g(mref, "Name", "name", "PhysicalName", "physicalName")
            else:
                mref_name = mref
            # Resolve by physical name match
            for attr_dict in attributes:
                if attr_dict["physical_name"] == mref_name or attr_dict["logical_name"] == mref_name:
                    member_ids.append(attr_dict["id"])
                    break
        if member_ids:
            keys.append(
                {
                    "id": f"{e_id}_k{k_idx}",
                    "name": _g(k, "Name", "name") or f"{k_type.lower()}_{physical}",
                    "key_type": k_type,
                    "members": member_ids,
                }
            )

    return {
        "id": e_id,
        "logical_name": str(logical),
        "physical_name": str(physical),
        "attributes": attributes,
        "keys": keys,
    }


# ── generic tables/columns adapter ───────────────────────────

def _adapt_tables(data: dict) -> dict[str, Any]:
    """Map `{tables: [{name, columns: [...]}]}` to native shape."""
    tables = data.get("tables") or []
    entities: list[dict[str, Any]] = []

    for i, t in enumerate(tables):
        if not isinstance(t, dict):
            continue
        t_name = _g(t, "name", "table_name", "tableName", "Name", default=f"table_{i}")
        e_id = f"e_{_slug(t_name)}_{i}"

        cols = _g(t, "columns", "Columns", "fields", "Fields", default=[])
        if not isinstance(cols, list):
            cols = []

        attributes: list[dict[str, Any]] = []
        pk_attr_ids: list[str] = []
        for j, c in enumerate(cols):
            if not isinstance(c, dict):
                continue
            c_name = _g(c, "name", "column_name", "columnName", "Name", default=f"col_{j}")
            c_type = _g(c, "type", "data_type", "dataType", "DataType", default="VARCHAR(255)")
            c_nullable = _g(c, "nullable", "Nullable", "is_nullable", default=True)
            if _g(c, "not_null", "NotNull", "required") is True:
                c_nullable = False

            a_id = f"{e_id}_a{j}"
            attributes.append(
                {
                    "id": a_id,
                    "logical_name": str(c_name),
                    "physical_name": str(c_name),
                    "data_type": str(c_type),
                    "is_nullable": bool(c_nullable),
                    "position": j + 1,
                }
            )
            if _g(c, "primary_key", "primaryKey", "is_pk", "pk", "isPk"):
                pk_attr_ids.append(a_id)

        keys: list[dict[str, Any]] = []
        if pk_attr_ids:
            keys.append(
                {
                    "id": f"{e_id}_pk",
                    "name": f"pk_{t_name}",
                    "key_type": "PK",
                    "members": pk_attr_ids,
                }
            )
        else:
            # Table-level PK declaration (`primary_key: ["col_a", "col_b"]`)
            tbl_pk = _g(t, "primary_key", "primaryKey", "pk")
            if tbl_pk:
                if isinstance(tbl_pk, str):
                    tbl_pk = [tbl_pk]
                if isinstance(tbl_pk, list):
                    member_ids = []
                    for pk_col_name in tbl_pk:
                        for attr in attributes:
                            if attr["physical_name"] == pk_col_name:
                                member_ids.append(attr["id"])
                                break
                    if member_ids:
                        keys.append(
                            {
                                "id": f"{e_id}_pk",
                                "name": f"pk_{t_name}",
                                "key_type": "PK",
                                "members": member_ids,
                            }
                        )

        entities.append(
            {
                "id": e_id,
                "logical_name": str(t_name),
                "physical_name": str(t_name),
                "attributes": attributes,
                "keys": keys,
            }
        )

    return {
        "name": data.get("name") or "Imported Tables",
        "model_type": "physical",
        "entities": entities,
    }
