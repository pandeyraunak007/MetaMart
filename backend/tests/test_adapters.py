"""Tests for the foreign-format adapter."""
from metamart.quality.adapters import normalize_catalog


def test_native_shape_passthrough():
    data = {"name": "X", "model_type": "physical", "entities": [{"id": "e1"}]}
    assert normalize_catalog(data) == data


def test_non_dict_passthrough():
    assert normalize_catalog([{"id": "e1"}]) == [{"id": "e1"}]
    assert normalize_catalog("nope") == "nope"


# ── erwin ─────────────────────────────────────────────────

def test_erwin_pascal_case():
    erwin_data = {
        "Model": {"Name": "Sales"},
        "Entities": [
            {
                "Name": "Customer",
                "PhysicalName": "customer",
                "Attributes": [
                    {"Name": "Customer ID", "PhysicalName": "customer_id",
                     "DataType": "BIGINT", "NotNull": True, "IsPK": True},
                    {"Name": "Email", "PhysicalName": "email", "DataType": "VARCHAR(320)"},
                ],
            }
        ],
        "Relationships": [
            {"Name": "customer_orders", "ParentEntity": "Customer",
             "ChildEntity": "Order", "Cardinality": "one_to_many"}
        ],
    }
    out = normalize_catalog(erwin_data)
    assert out["name"] == "Sales"
    e = out["entities"][0]
    assert e["physical_name"] == "customer"
    assert len(e["attributes"]) == 2
    assert e["attributes"][0]["is_nullable"] is False
    assert len(e["keys"]) == 1
    assert out["relationships"][0]["parent"] == "e_customer"


def test_erwin_explicit_keys_block():
    data = {
        "Entities": [
            {
                "Name": "Product", "PhysicalName": "product",
                "Attributes": [
                    {"PhysicalName": "product_id", "DataType": "BIGINT"},
                    {"PhysicalName": "sku", "DataType": "VARCHAR(64)"},
                ],
                "Keys": [{"Type": "PK", "Name": "pk_product", "Members": ["product_id"]}],
            }
        ]
    }
    out = normalize_catalog(data)
    assert out["entities"][0]["keys"][0]["key_type"] == "PK"


def test_erwin_nested_model_block():
    data = {
        "ERwinModel": {
            "Name": "Inventory",
            "Entity": [
                {"Name": "Item", "PhysicalName": "item",
                 "Attribute": [{"PhysicalName": "item_id", "DataType": "BIGINT", "IsPK": True}]}
            ],
        }
    }
    out = normalize_catalog(data)
    assert out["name"] == "Inventory"
    assert out["entities"][0]["physical_name"] == "item"


# ── tables/columns ────────────────────────────────────────

def test_tables_columns_shape():
    data = {
        "tables": [
            {"name": "users", "columns": [
                {"name": "user_id", "type": "BIGINT", "primary_key": True},
                {"name": "email", "type": "VARCHAR(255)", "nullable": False},
            ]},
            {"name": "orders", "columns": [{"name": "order_id", "data_type": "BIGINT"}],
             "primary_key": ["order_id"]},
        ]
    }
    out = normalize_catalog(data)
    assert len(out["entities"]) == 2
    users = next(e for e in out["entities"] if e["physical_name"] == "users")
    orders = next(e for e in out["entities"] if e["physical_name"] == "orders")
    assert users["attributes"][1]["is_nullable"] is False
    assert len(users["keys"]) == 1
    assert len(orders["keys"]) == 1


# ── dbt manifest ──────────────────────────────────────────

def test_dbt_manifest_with_columns_dict():
    data = {
        "metadata": {"project_name": "analytics"},
        "nodes": {
            "model.analytics.users": {
                "name": "users", "resource_type": "model",
                "columns": {
                    "user_id": {"name": "user_id", "data_type": "BIGINT"},
                    "email": {"name": "email", "data_type": "VARCHAR(320)"},
                },
            },
            "model.analytics.orders": {
                "name": "orders", "resource_type": "model",
                "columns": {"order_id": {"name": "order_id", "data_type": "BIGINT"}},
            },
        },
        "sources": {},
    }
    out = normalize_catalog(data)
    assert out["name"] == "analytics"
    names = {e["physical_name"] for e in out["entities"]}
    assert names == {"users", "orders"}
    users = next(e for e in out["entities"] if e["physical_name"] == "users")
    assert len(users["attributes"]) == 2


# ── polymorphic objects ───────────────────────────────────

def test_polymorphic_objects_array():
    data = {
        "objects": [
            {"type": "Entity", "name": "Customer", "physicalName": "customer",
             "properties": {"id": {"type": "BIGINT"}, "email": {"type": "VARCHAR"}}},
            {"type": "Entity", "name": "Order", "physicalName": "order_header",
             "properties": {"order_id": {"type": "BIGINT"}}},
            {"type": "Relationship", "parent": "Customer", "child": "Order"},
        ]
    }
    out = normalize_catalog(data)
    assert len(out["entities"]) == 2
    assert len(out["relationships"]) == 1


def test_polymorphic_objects_list_properties():
    data = {
        "objects": [
            {"type": "Entity", "name": "Foo", "physicalName": "foo",
             "attributes": [
                 {"name": "a", "type": "INTEGER"},
                 {"name": "b", "type": "TEXT"},
             ]}
        ]
    }
    out = normalize_catalog(data)
    assert len(out["entities"][0]["attributes"]) == 2


# ── OpenAPI / JSON Schema ─────────────────────────────────

def test_openapi_components_schemas():
    data = {
        "openapi": "3.0.0",
        "info": {"title": "Users API"},
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "format": "int64"},
                        "email": {"type": "string"},
                        "created_at": {"type": "string", "format": "date-time"},
                    },
                    "required": ["id"],
                },
                "Order": {
                    "type": "object",
                    "properties": {"order_id": {"type": "integer"}},
                    "required": ["order_id"],
                },
            }
        },
    }
    out = normalize_catalog(data)
    assert out["name"] == "Users API"
    names = {e["logical_name"] for e in out["entities"]}
    assert names == {"User", "Order"}
    user = next(e for e in out["entities"] if e["logical_name"] == "User")
    assert user["physical_name"] == "user"
    # id has int64 → BIGINT
    id_attr = next(a for a in user["attributes"] if a["physical_name"] == "id")
    assert id_attr["data_type"] == "BIGINT"
    assert id_attr["is_nullable"] is False  # in required
    # email is optional
    email_attr = next(a for a in user["attributes"] if a["physical_name"] == "email")
    assert email_attr["is_nullable"] is True


def test_swagger2_definitions():
    data = {
        "swagger": "2.0",
        "definitions": {
            "Customer": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                "required": ["id"],
            }
        },
    }
    out = normalize_catalog(data)
    assert len(out["entities"]) == 1


# ── generic walker (last resort) ──────────────────────────

def test_generic_walker_finds_nested_entities():
    data = {
        "database": {
            "schema": {
                "Customer": {
                    "fields": [
                        {"name": "id", "type": "BIGINT"},
                        {"name": "email", "type": "VARCHAR(255)"},
                    ]
                },
                "Order": {"fields": [{"name": "order_id", "type": "BIGINT"}]},
            }
        }
    }
    out = normalize_catalog(data)
    physical_names = {e["physical_name"] for e in out["entities"]}
    assert physical_names == {"Customer", "Order"}


def test_generic_walker_uses_parent_key_as_name_fallback():
    data = {
        "schemas": {
            "user_profile": {
                "columns": [{"name": "id", "type": "BIGINT"}, {"name": "bio", "type": "TEXT"}]
            }
        }
    }
    out = normalize_catalog(data)
    assert len(out["entities"]) == 1
    assert out["entities"][0]["physical_name"] == "user_profile"


def test_generic_walker_handles_columns_as_dict():
    data = {
        "models": {
            "post": {
                "columns": {
                    "id": {"type": "BIGINT"},
                    "title": {"type": "VARCHAR(256)"},
                }
            }
        }
    }
    out = normalize_catalog(data)
    e = out["entities"][0]
    assert e["physical_name"] == "post"
    assert {a["physical_name"] for a in e["attributes"]} == {"id", "title"}


def test_unknown_shape_returns_unchanged():
    """A JSON with no name/columns hints anywhere should pass through unchanged
    so catalog_from_json's own error message fires."""
    data = {"foo": "bar", "baz": 42}
    out = normalize_catalog(data)
    assert out == data


# ── end-to-end ────────────────────────────────────────────

def test_erwin_15x_save_as_json_format():
    """erwin DM 15.x 'Save Model As JSON' export — wrapped under Objects.Entity,
    Attributes as {Attribute: [...]}, Physical_Name / Null_Option / Key_Type."""
    data = {
        "version": "1.0",
        "Encoding": "UTF-8",
        "Description": "This is erwin Generated JSON File. This file is having all the object related informations",
        "Model_Information": {
            "Model_Name": "Sales DB",
            "Database_Type": "SQL Server",
        },
        "Objects": {
            "Entity": [
                {
                    "Id": "E1",
                    "Name": "Customer",
                    "Logical_Name": "Customer",
                    "Physical_Name": "Customer",
                    "Attributes": {
                        "Attribute": [
                            {
                                "Id": "A1",
                                "Name": "CustomerId",
                                "Logical_Name": "Customer Id",
                                "Physical_Name": "CustomerId",
                                "Logical_Data_Type": "Number(10,0)",
                                "Physical_Data_Type": "INT",
                                "Null_Option": "NOT NULL",
                                "Key_Type": "PRIMARY KEY",
                            },
                            {
                                "Id": "A2",
                                "Name": "Email",
                                "Logical_Name": "Email",
                                "Physical_Name": "Email",
                                "Physical_Data_Type": "VARCHAR(320)",
                                "Null_Option": "NULL",
                            },
                        ]
                    },
                },
                {
                    "Id": "E2",
                    "Name": "Order",
                    "Logical_Name": "Order",
                    "Physical_Name": "OrderHeader",
                    "Attributes": {
                        "Attribute": [
                            {
                                "Id": "A3",
                                "Name": "OrderId",
                                "Physical_Name": "OrderId",
                                "Physical_Data_Type": "INT",
                                "Null_Option": "NOT NULL",
                                "Key_Type": "PRIMARY KEY",
                            }
                        ]
                    },
                },
            ],
            "Relationship": [
                {
                    "Name": "customer_orders",
                    "ParentEntity": "Customer",
                    "ChildEntity": "Order",
                }
            ],
        },
    }
    out = normalize_catalog(data)
    assert out["name"] == "Sales DB"
    assert len(out["entities"]) == 2
    customer = next(e for e in out["entities"] if e["physical_name"] == "Customer")
    assert customer["logical_name"] == "Customer"
    assert len(customer["attributes"]) == 2
    cust_id = next(a for a in customer["attributes"] if a["physical_name"] == "CustomerId")
    assert cust_id["data_type"] == "INT"
    assert cust_id["is_nullable"] is False
    assert len(customer["keys"]) == 1
    assert customer["keys"][0]["key_type"] == "PK"


def test_catalog_wrapper_detection():
    from metamart.quality.adapters import looks_like_catalog_wrapper
    assert looks_like_catalog_wrapper({"version": "1.0", "Description": "..."})
    assert looks_like_catalog_wrapper({"Objects": {}})
    assert looks_like_catalog_wrapper({"Model": {}, "metadata": {}})
    assert not looks_like_catalog_wrapper({"Name": "X", "Attributes": []})  # an entity
    assert not looks_like_catalog_wrapper("not a dict")


def test_erwin_via_engine_produces_a_grade():
    import metamart.quality  # noqa: F401  -- register rules
    from metamart.quality.engine import score_catalog
    from metamart.quality.ingest_json import catalog_from_json
    from metamart.quality.pack import default_pack

    erwin_data = {
        "Model": {"Name": "Demo"},
        "Entities": [
            {"Name": "Customer", "PhysicalName": "customer",
             "Attributes": [
                 {"Name": "Customer ID", "PhysicalName": "customer_id",
                  "DataType": "BIGINT", "IsPK": True, "NotNull": True}
             ]}
        ],
    }
    snapshot = catalog_from_json(erwin_data)
    result = score_catalog(snapshot, default_pack())
    assert result.grade in {"A", "B", "C", "D", "F"}
