"""Normalize various JSON catalog shapes into MetaMart's native format.

Detection cascade (most specific → most general):
  1. Native MetaMart shape — passthrough.
  2. erwin Data Modeler exports — PascalCase keys, `Entities`/`Attributes`.
  3. Generic SQL-ish dumps — `{tables: [{name, columns: [...]}]}`.
  4. dbt manifest.json — `{metadata, nodes: {id: {columns: {...}}}}`.
  5. erwin DAS-style polymorphic — `{objects: [{type: "Entity"|"Relationship"}]}`.
  6. OpenAPI / JSON Schema — `{components: {schemas: {Name: {properties: ...}}}}`.
  7. Generic recursive walker — finds any dict with a name + column-like collection.

Anything that still doesn't match falls through and `catalog_from_json` raises
an informative error listing the actual top-level keys seen.
"""
from __future__ import annotations

from typing import Any

# ── shared name pools ─────────────────────────────────────────

_NAME_KEYS = (
    "name", "Name",
    "Logical_Name", "logical_name",
    "LogicalName", "logicalName",
    "tableName", "TableName",
    "EntityName", "entityName",
    "label", "title",
)
_PHYSICAL_NAME_KEYS = (
    "PhysicalName", "physicalName",
    "Physical_Name", "physical_name",
    "TableName", "tableName",
    "ColumnName", "columnName",
    "Column_Name", "column_name",
)
_LOGICAL_NAME_KEYS = (
    "LogicalName", "logicalName",
    "Logical_Name", "logical_name",
    "DisplayName", "displayName",
    "Label", "label",
)
_ATTR_COLLECTION_KEYS = (
    "attributes", "Attributes",
    "columns", "Columns",
    "fields", "Fields",
    "properties", "Properties",
    "Attribute", "Column",
)
_DATATYPE_KEYS = (
    "DataType", "dataType", "data_type",
    "Data_Type", "data type",
    "Type", "type",
    "Datatype", "datatype",
    "PhysicalDataType", "physicalDataType",
    "Physical_Data_Type", "physical_data_type",
    "Logical_Data_Type", "logical_data_type",
)
_NULLABLE_NEG_KEYS = ("NotNull", "notNull", "IsNotNull", "isNotNull", "Required", "required")
_NULLABLE_POS_KEYS = ("Nullable", "nullable", "IsNullable", "isNullable")
_PK_FLAG_KEYS = (
    "IsPK", "isPK", "isPk",
    "IsPrimaryKey", "isPrimaryKey",
    "PrimaryKey", "primary_key", "primaryKey",
    "pk",
)
# Single-key wrappers used by erwin "Save As JSON" (e.g. {"Entity": [...]}).
_ENTITY_INNER_KEYS = ("Entity", "Entities", "entity", "entities", "Table", "Tables", "table", "tables")
_ATTR_INNER_KEYS = ("Attribute", "Attributes", "attribute", "attributes", "Column", "Columns", "column", "columns")


# ── top-level entry point ─────────────────────────────────────

def normalize_catalog(data: Any) -> Any:
    """Convert known foreign shapes to native catalog format. Idempotent.

    Adapters are tried in order of specificity. Each one that *recognizes* the
    shape produces a candidate; only candidates with non-empty `entities`
    count. If no specific adapter produced entities, the generic walker is
    run as a last resort. We then pick the candidate with the most entities
    (a stronger signal of a correct match than just shape recognition).
    """
    if not isinstance(data, dict):
        return data
    if "entities" in data and isinstance(data["entities"], list):
        return data

    candidates: list[dict[str, Any]] = []

    def _try(check, adapt) -> None:
        try:
            if check(data):
                result = adapt(data)
                if isinstance(result, dict) and result.get("entities"):
                    candidates.append(result)
        except Exception:
            # An adapter mis-fire shouldn't poison the whole pipeline.
            pass

    _try(_looks_like_erwin, _adapt_erwin)
    _try(lambda d: "tables" in d and isinstance(d["tables"], list), _adapt_tables)
    _try(_looks_like_dbt, _adapt_dbt)
    _try(_looks_like_polymorphic, _adapt_polymorphic_objects)
    _try(_looks_like_openapi, _adapt_openapi)

    # Generic walker — always try it as another candidate; for nested erwin
    # shapes that our specific adapter missed, this often finds the entities.
    discovered = _walk_for_entities(data)
    if discovered:
        candidates.append(
            {
                "name": _g(data, "name", "Name", "title", "Title", default="Auto-detected model"),
                "model_type": "physical",
                "entities": discovered,
            }
        )

    if candidates:
        # Prefer the adapter that found the most entities.
        return max(candidates, key=lambda c: len(c["entities"]))

    return data


# ── helpers ──────────────────────────────────────────────────

def _g(d: Any, *keys: str, default: Any = None) -> Any:
    """First non-None value among the given keys (case variations)."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _slug(name: Any) -> str:
    if not name:
        return "unknown"
    return (
        str(name)
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "_")
        .replace("/", "_")
    )


def _entity_id_from_ref(ref: Any) -> str:
    if isinstance(ref, dict):
        return f"e_{_slug(_g(ref, *_NAME_KEYS, *_PHYSICAL_NAME_KEYS))}"
    return f"e_{_slug(str(ref))}"


def _resolve_nullable(a: dict) -> bool:
    if _g(a, *_NULLABLE_NEG_KEYS) is True:
        return False
    if _g(a, *_NULLABLE_POS_KEYS) is False:
        return False
    # erwin "Save As JSON" 15.x uses `Null_Option`: "NOT NULL" / "NULL"
    null_opt = _g(a, "Null_Option", "null_option", "NullOption", "nullOption", default="")
    if isinstance(null_opt, str) and "NOT" in null_opt.upper():
        return False
    return True


def _is_primary_key(a: dict) -> bool:
    """True if an attribute dict signals primary-key membership."""
    if _g(a, *_PK_FLAG_KEYS):
        return True
    # erwin 15.x "Save As JSON" uses Key_Type: "PRIMARY KEY" / "FOREIGN KEY"
    key_type = _g(a, "Key_Type", "key_type", "KeyType", "keyType", "Key", default="")
    if isinstance(key_type, str) and key_type.strip().upper() in {
        "PK", "PRIMARY KEY", "PRIMARY"
    }:
        return True
    return False


def _flatten_collection(raw: Any, inner_keys: tuple[str, ...]) -> list[Any]:
    """Flatten erwin-style nested dict {Entity: [...]} into a plain list."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for k in inner_keys:
            if k in raw:
                v = raw[k]
                if isinstance(v, list):
                    return v
                if isinstance(v, dict):
                    return [v]
    return []


# Top-level keys that strongly suggest a whole-catalog wrapper (not a single entity).
_CATALOG_WRAPPER_KEYS = {
    "version", "encoding", "description", "metadata",
    "model", "model_information", "modelinformation",
    "objects", "mart_information", "martinformation",
    "entities", "tables", "nodes",
    "components", "definitions", "schemas",
    "erwinmodel", "datamodel",
}


def looks_like_catalog_wrapper(d: Any) -> bool:
    """Does this dict look like a whole-catalog wrapper (rather than a single entity)?

    Used by the API endpoint to decide whether to unwrap a single-element list
    or treat the list as a bare entities array.
    """
    if not isinstance(d, dict):
        return False
    lowered = {str(k).lower() for k in d.keys()}
    return bool(lowered & _CATALOG_WRAPPER_KEYS)


# ── erwin adapter (PascalCase Entities/Attributes) ───────────

def _looks_like_erwin(data: dict) -> bool:
    # Direct: top-level Entities/ERwinModel/DataModel/Entity
    if any(k in data for k in ("Entities", "ERwinModel", "erwinModel", "DataModel", "Entity")):
        return True
    # erwin 15.x "Save As JSON" wrapper: Description mentions "erwin"
    desc = _g(data, "Description", "description", default="")
    if isinstance(desc, str) and "erwin" in desc.lower():
        return True
    # Nested under Objects key with Entity/Table children
    objs = _g(data, "Objects", "objects")
    if isinstance(objs, dict) and any(k in objs for k in _ENTITY_INNER_KEYS):
        return True
    # Nested under Model.Entities
    model = _g(data, "Model", "model", "Model_Information", "model_information")
    if isinstance(model, dict) and any(k in model for k in _ENTITY_INNER_KEYS):
        return True
    return False


def _adapt_erwin(data: dict) -> dict[str, Any]:
    # Locate the model-info block (erwin 15.x uses "Model_Information")
    model_block = _g(
        data,
        "Model",
        "Model_Information", "model_information",
        "ERwinModel", "erwinModel",
        "DataModel",
        default={},
    )
    objs_block = _g(data, "Objects", "objects", default={})

    model_name = (
        _g(data, "Name", "ModelName", "name", "modelName")
        or _g(model_block, "Name", "ModelName", "name", "modelName", "Model_Name", "model_name")
        or _g(data, "Description", "description")
    )

    # Entities can live at any of: data root, model_block, or objs_block.
    raw_entities: Any = (
        _g(data, "Entities", "Tables", "entities", "tables")
        or _g(model_block, *_ENTITY_INNER_KEYS)
        or _g(objs_block, *_ENTITY_INNER_KEYS)
    )
    # erwin sometimes wraps the list in a single-key dict like {"Entity": [...]}
    raw_entities = _flatten_collection(raw_entities, _ENTITY_INNER_KEYS)

    entities = [_adapt_erwin_entity(e, i) for i, e in enumerate(raw_entities) if isinstance(e, dict)]

    # Relationships similarly can be in several locations.
    raw_rels: Any = (
        _g(data, "Relationships", "relationships")
        or _g(model_block, "Relationship", "Relationships", "relationship", "relationships")
        or _g(objs_block, "Relationship", "Relationships", "relationship", "relationships")
    )
    raw_rels = _flatten_collection(raw_rels, ("Relationship", "Relationships", "relationship", "relationships"))

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
    logical = _g(e, *_LOGICAL_NAME_KEYS, *_NAME_KEYS, default=f"Entity{idx}")
    physical = _g(e, *_PHYSICAL_NAME_KEYS, *_NAME_KEYS, default=logical)
    e_id = f"e_{_slug(physical or logical)}_{idx}"

    # erwin 15.x nests as Attributes: {Attribute: [...]} — flatten that.
    raw_attrs = _flatten_collection(_g(e, *_ATTR_COLLECTION_KEYS), _ATTR_INNER_KEYS)

    attributes: list[dict[str, Any]] = []
    pk_attr_ids: list[str] = []
    for j, a in enumerate(raw_attrs):
        if not isinstance(a, dict):
            continue
        a_logical = _g(a, *_LOGICAL_NAME_KEYS, *_NAME_KEYS, default=f"attr_{j}")
        a_physical = _g(a, *_PHYSICAL_NAME_KEYS, *_NAME_KEYS, default=a_logical)
        a_type = _g(a, *_DATATYPE_KEYS, default="VARCHAR(255)")
        is_nullable = _resolve_nullable(a)
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
        if _is_primary_key(a):
            pk_attr_ids.append(a_id)

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

    raw_keys = _g(e, "Keys", "keys", "Key_Group", "key_group", default=[])
    raw_keys = _flatten_collection(raw_keys, ("Key", "Keys", "key", "keys", "Key_Group", "key_group"))
    for k_idx, k in enumerate(raw_keys):
        if not isinstance(k, dict):
            continue
        k_type = str(_g(k, "Type", "type", "KeyType", "keyType", default="PK")).upper()
        if k_type not in ("PK", "AK", "IE"):
            continue
        if k_type == "PK" and pk_attr_ids:
            continue
        member_refs = _g(k, "Members", "members", "Attributes", "attributes", default=[])
        if not isinstance(member_refs, list):
            continue
        member_ids: list[str] = []
        for mref in member_refs:
            mref_name = _g(mref, "Name", "name", "PhysicalName", "physicalName") if isinstance(mref, dict) else mref
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
    tables = data.get("tables") or []
    entities: list[dict[str, Any]] = []

    for i, t in enumerate(tables):
        if not isinstance(t, dict):
            continue
        t_name = _g(t, *_NAME_KEYS, default=f"table_{i}")
        e_id = f"e_{_slug(t_name)}_{i}"

        cols = _g(t, *_ATTR_COLLECTION_KEYS, default=[])
        if not isinstance(cols, list):
            cols = []

        attributes: list[dict[str, Any]] = []
        pk_attr_ids: list[str] = []
        for j, c in enumerate(cols):
            if not isinstance(c, dict):
                continue
            c_name = _g(c, *_NAME_KEYS, *_PHYSICAL_NAME_KEYS, default=f"col_{j}")
            c_type = _g(c, *_DATATYPE_KEYS, default="VARCHAR(255)")
            c_nullable = _resolve_nullable(c)
            a_id = f"{e_id}_a{j}"
            attributes.append(
                {
                    "id": a_id,
                    "logical_name": str(c_name),
                    "physical_name": str(c_name),
                    "data_type": str(c_type),
                    "is_nullable": c_nullable,
                    "position": j + 1,
                }
            )
            if _g(c, *_PK_FLAG_KEYS):
                pk_attr_ids.append(a_id)

        keys: list[dict[str, Any]] = []
        if pk_attr_ids:
            keys.append({"id": f"{e_id}_pk", "name": f"pk_{t_name}", "key_type": "PK", "members": pk_attr_ids})
        else:
            tbl_pk = _g(t, "primary_key", "primaryKey", "pk")
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
                    keys.append({"id": f"{e_id}_pk", "name": f"pk_{t_name}", "key_type": "PK", "members": member_ids})

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


# ── dbt manifest.json adapter ────────────────────────────────

def _looks_like_dbt(data: dict) -> bool:
    return (
        ("nodes" in data and isinstance(data["nodes"], dict))
        or ("sources" in data and isinstance(data["sources"], dict))
    )


def _adapt_dbt(data: dict) -> dict[str, Any]:
    pool: dict[str, Any] = {}
    pool.update(data.get("sources") or {})
    pool.update(data.get("nodes") or {})

    entities: list[dict[str, Any]] = []
    for i, (node_id, node) in enumerate(pool.items()):
        if not isinstance(node, dict):
            continue
        resource_type = node.get("resource_type")
        if resource_type not in (None, "model", "source", "seed", "snapshot"):
            continue

        e_name = node.get("name") or str(node_id).split(".")[-1]
        e_id = f"e_{_slug(e_name)}_{i}"

        cols = node.get("columns", {})
        attributes: list[dict[str, Any]] = []
        if isinstance(cols, dict):
            for j, (col_name, col) in enumerate(cols.items()):
                if not isinstance(col, dict):
                    continue
                attributes.append(
                    {
                        "id": f"{e_id}_a{j}",
                        "logical_name": col.get("name") or col_name,
                        "physical_name": col.get("name") or col_name,
                        "data_type": col.get("data_type") or "VARCHAR(255)",
                        "is_nullable": True,
                        "position": j + 1,
                    }
                )

        entities.append(
            {
                "id": e_id,
                "logical_name": e_name,
                "physical_name": e_name,
                "attributes": attributes,
                "keys": [],
            }
        )

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    return {
        "name": metadata.get("project_name") or "dbt manifest",
        "model_type": "physical",
        "entities": entities,
    }


# ── polymorphic objects adapter (erwin DAS-like) ─────────────

def _looks_like_polymorphic(data: dict) -> bool:
    objs = data.get("objects")
    if not isinstance(objs, list) or not objs:
        return False
    return any(isinstance(o, dict) and "type" in o for o in objs[:5])


def _adapt_polymorphic_objects(data: dict) -> dict[str, Any]:
    objs = data.get("objects", [])
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    name_to_id: dict[str, str] = {}

    for i, obj in enumerate(objs):
        if not isinstance(obj, dict):
            continue
        obj_type = str(obj.get("type", "")).lower()

        if obj_type in ("entity", "table"):
            e_name = _g(obj, *_NAME_KEYS, default=f"entity_{i}")
            e_physical = _g(obj, *_PHYSICAL_NAME_KEYS, default=e_name)
            e_id = f"e_{_slug(e_physical)}_{i}"
            name_to_id[e_name] = e_id

            raw_props = _g(obj, *_ATTR_COLLECTION_KEYS, default={})
            attributes: list[dict[str, Any]] = []

            if isinstance(raw_props, dict):
                for j, (col_key, c) in enumerate(raw_props.items()):
                    attr = _attr_from_value(col_key, c, f"{e_id}_a{j}", j)
                    if attr is not None:
                        attributes.append(attr)
            elif isinstance(raw_props, list):
                for j, c in enumerate(raw_props):
                    if not isinstance(c, dict):
                        continue
                    attr = _attr_from_value(_g(c, *_NAME_KEYS, default=f"col_{j}"), c, f"{e_id}_a{j}", j)
                    if attr is not None:
                        attributes.append(attr)

            entities.append(
                {
                    "id": e_id,
                    "logical_name": str(e_name),
                    "physical_name": str(e_physical),
                    "attributes": attributes,
                    "keys": [],
                }
            )

        elif obj_type in ("relationship", "fk"):
            parent_ref = _g(obj, "parent", "Parent", "from", "From", "ParentEntity")
            child_ref = _g(obj, "child", "Child", "to", "To", "ChildEntity")
            if not parent_ref or not child_ref:
                continue
            relationships.append(
                {
                    "id": f"r{i}",
                    "name": _g(obj, *_NAME_KEYS),
                    "parent": name_to_id.get(str(parent_ref), _entity_id_from_ref(parent_ref)),
                    "child": name_to_id.get(str(child_ref), _entity_id_from_ref(child_ref)),
                }
            )

    return {
        "name": _g(data, *_NAME_KEYS, default="Polymorphic objects import"),
        "model_type": "physical",
        "entities": entities,
        "relationships": relationships,
    }


def _attr_from_value(name_hint: Any, value: Any, attr_id: str, j: int) -> dict[str, Any] | None:
    """Build one attribute dict from a (name, value-or-dict) pair."""
    if isinstance(value, dict):
        a_name = _g(value, *_NAME_KEYS, *_PHYSICAL_NAME_KEYS) or name_hint
        a_type = _g(value, *_DATATYPE_KEYS, default="VARCHAR(255)")
        a_nullable = _resolve_nullable(value)
    else:
        a_name = name_hint
        a_type = str(value) if value else "VARCHAR(255)"
        a_nullable = True
    if not a_name:
        return None
    return {
        "id": attr_id,
        "logical_name": str(a_name),
        "physical_name": str(a_name),
        "data_type": str(a_type),
        "is_nullable": bool(a_nullable),
        "position": j + 1,
    }


# ── OpenAPI / JSON Schema adapter ────────────────────────────

def _looks_like_openapi(data: dict) -> bool:
    if "openapi" in data or "swagger" in data:
        return True
    if "components" in data and isinstance(data.get("components"), dict):
        schemas = data["components"].get("schemas")
        if isinstance(schemas, dict):
            return True
    if "definitions" in data and isinstance(data["definitions"], dict):
        return True  # Swagger 2 / JSON Schema draft
    if data.get("type") == "object" and isinstance(data.get("properties"), dict):
        return True
    return False


def _adapt_openapi(data: dict) -> dict[str, Any]:
    schemas: dict[str, Any] = {}
    if isinstance(data.get("components"), dict):
        schemas.update(data["components"].get("schemas") or {})
    if isinstance(data.get("definitions"), dict):
        schemas.update(data["definitions"])
    if not schemas and data.get("type") == "object":
        schemas[data.get("title", "Schema")] = data

    entities: list[dict[str, Any]] = []
    for i, (schema_name, schema) in enumerate(schemas.items()):
        if not isinstance(schema, dict):
            continue
        if schema.get("type") not in (None, "object"):
            continue

        props = schema.get("properties", {})
        if not isinstance(props, dict):
            continue
        required = set(schema.get("required") or [])
        e_id = f"e_{_slug(schema_name)}_{i}"

        attributes: list[dict[str, Any]] = []
        for j, (prop_name, prop) in enumerate(props.items()):
            if not isinstance(prop, dict):
                continue
            attributes.append(
                {
                    "id": f"{e_id}_a{j}",
                    "logical_name": prop_name,
                    "physical_name": prop_name,
                    "data_type": _openapi_type(prop),
                    "is_nullable": prop_name not in required,
                    "position": j + 1,
                }
            )

        entities.append(
            {
                "id": e_id,
                "logical_name": str(schema_name),
                "physical_name": _slug(schema_name),
                "attributes": attributes,
                "keys": [],
            }
        )

    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    return {
        "name": info.get("title") or "OpenAPI import",
        "model_type": "logical",
        "entities": entities,
    }


def _openapi_type(prop: dict) -> str:
    t = prop.get("type", "object")
    fmt = prop.get("format", "")
    if t == "integer":
        return "BIGINT" if fmt == "int64" else "INTEGER"
    if t == "number":
        return "NUMERIC"
    if t == "boolean":
        return "BOOLEAN"
    if t == "string":
        if fmt == "date-time":
            return "TIMESTAMPTZ"
        if fmt == "date":
            return "DATE"
        if fmt == "uuid":
            return "UUID"
        return "VARCHAR(255)"
    if t == "array":
        return "ARRAY"
    return "JSONB"


# ── generic recursive walker (last resort) ───────────────────

def _has_name(obj: dict) -> bool:
    return any(k in obj for k in _NAME_KEYS + _PHYSICAL_NAME_KEYS)


def _has_attr_collection(obj: dict) -> bool:
    for k in _ATTR_COLLECTION_KEYS:
        if k in obj:
            coll = obj[k]
            if isinstance(coll, list) and coll and any(isinstance(x, dict) for x in coll):
                return True
            if isinstance(coll, dict) and coll:
                return True
    return False


def _walk_for_entities(
    data: Any,
    key_hint: str = "",
    max_depth: int = 6,
    seen_physicals: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Best-effort: find any dict with a name + column-like collection."""
    if seen_physicals is None:
        seen_physicals = set()
    if max_depth <= 0:
        return []
    out: list[dict[str, Any]] = []

    if isinstance(data, dict):
        if _has_attr_collection(data) and (_has_name(data) or key_hint):
            extracted = _extract_entity(data, key_hint, idx=len(seen_physicals))
            if extracted["physical_name"] not in seen_physicals:
                seen_physicals.add(extracted["physical_name"])
                out.append(extracted)
            return out  # don't recurse INTO an entity
        for k, v in data.items():
            out.extend(_walk_for_entities(v, k, max_depth - 1, seen_physicals))
    elif isinstance(data, list):
        for item in data:
            out.extend(_walk_for_entities(item, key_hint, max_depth - 1, seen_physicals))
    return out


def _extract_entity(obj: dict, key_hint: str, idx: int) -> dict[str, Any]:
    name = _g(obj, *_NAME_KEYS) or key_hint or f"entity_{idx}"
    physical = _g(obj, *_PHYSICAL_NAME_KEYS) or name
    e_id = f"e_{_slug(physical)}_{idx}"

    cols: Any = []
    for k in _ATTR_COLLECTION_KEYS:
        if k in obj:
            cols = obj[k]
            break

    attributes: list[dict[str, Any]] = []
    if isinstance(cols, list):
        for j, c in enumerate(cols):
            if not isinstance(c, dict):
                continue
            c_name = _g(c, *_NAME_KEYS, *_PHYSICAL_NAME_KEYS, default=f"col_{j}")
            attributes.append(
                {
                    "id": f"{e_id}_a{j}",
                    "logical_name": str(c_name),
                    "physical_name": str(c_name),
                    "data_type": str(_g(c, *_DATATYPE_KEYS, default="VARCHAR(255)")),
                    "is_nullable": _resolve_nullable(c),
                    "position": j + 1,
                }
            )
    elif isinstance(cols, dict):
        for j, (col_key, c) in enumerate(cols.items()):
            attr = _attr_from_value(col_key, c, f"{e_id}_a{j}", j)
            if attr is not None:
                attributes.append(attr)

    return {
        "id": e_id,
        "logical_name": str(name),
        "physical_name": str(physical),
        "attributes": attributes,
        "keys": [],
    }
