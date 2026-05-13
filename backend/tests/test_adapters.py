"""Tests for the foreign-format adapter."""
from metamart.quality.adapters import normalize_catalog


def test_native_shape_passthrough():
    data = {"name": "X", "model_type": "physical", "entities": [{"id": "e1"}]}
    assert normalize_catalog(data) == data


def test_non_dict_passthrough():
    # Lists are wrapped in the router, not the adapter
    assert normalize_catalog([{"id": "e1"}]) == [{"id": "e1"}]
    assert normalize_catalog("nope") == "nope"


def test_erwin_pascal_case():
    erwin_data = {
        "Model": {"Name": "Sales"},
        "Entities": [
            {
                "Name": "Customer",
                "PhysicalName": "customer",
                "Attributes": [
                    {
                        "Name": "Customer ID",
                        "PhysicalName": "customer_id",
                        "DataType": "BIGINT",
                        "NotNull": True,
                        "IsPK": True,
                    },
                    {
                        "Name": "Email",
                        "PhysicalName": "email",
                        "DataType": "VARCHAR(320)",
                    },
                ],
            }
        ],
        "Relationships": [
            {
                "Name": "customer_orders",
                "ParentEntity": "Customer",
                "ChildEntity": "Order",
                "Cardinality": "one_to_many",
            }
        ],
    }
    out = normalize_catalog(erwin_data)
    assert out["name"] == "Sales"
    assert out["model_type"] == "physical"
    assert len(out["entities"]) == 1

    e = out["entities"][0]
    assert e["physical_name"] == "customer"
    assert e["logical_name"] == "Customer"
    assert len(e["attributes"]) == 2
    assert e["attributes"][0]["physical_name"] == "customer_id"
    assert e["attributes"][0]["data_type"] == "BIGINT"
    assert e["attributes"][0]["is_nullable"] is False
    assert len(e["keys"]) == 1
    assert e["keys"][0]["key_type"] == "PK"
    assert len(e["keys"][0]["members"]) == 1

    assert len(out["relationships"]) == 1
    assert out["relationships"][0]["parent"] == "e_customer"


def test_erwin_explicit_keys_block_resolves_by_name():
    data = {
        "Entities": [
            {
                "Name": "Product",
                "PhysicalName": "product",
                "Attributes": [
                    {"PhysicalName": "product_id", "DataType": "BIGINT"},
                    {"PhysicalName": "sku", "DataType": "VARCHAR(64)"},
                ],
                "Keys": [
                    {"Type": "PK", "Name": "pk_product", "Members": ["product_id"]}
                ],
            }
        ]
    }
    out = normalize_catalog(data)
    e = out["entities"][0]
    assert len(e["keys"]) == 1
    assert e["keys"][0]["key_type"] == "PK"


def test_tables_columns_shape():
    data = {
        "tables": [
            {
                "name": "users",
                "columns": [
                    {"name": "user_id", "type": "BIGINT", "primary_key": True},
                    {"name": "email", "type": "VARCHAR(255)", "nullable": False},
                ],
            },
            {
                "name": "orders",
                "columns": [{"name": "order_id", "data_type": "BIGINT"}],
                "primary_key": ["order_id"],
            },
        ]
    }
    out = normalize_catalog(data)
    assert len(out["entities"]) == 2
    users = next(e for e in out["entities"] if e["physical_name"] == "users")
    orders = next(e for e in out["entities"] if e["physical_name"] == "orders")

    assert len(users["attributes"]) == 2
    assert users["attributes"][1]["is_nullable"] is False
    assert len(users["keys"]) == 1
    assert users["keys"][0]["key_type"] == "PK"

    # Table-level primary_key list was honored
    assert len(orders["keys"]) == 1
    assert orders["keys"][0]["members"]


def test_erwin_nested_model_block():
    data = {
        "ERwinModel": {
            "Name": "Inventory",
            "Entity": [
                {
                    "Name": "Item",
                    "PhysicalName": "item",
                    "Attribute": [
                        {"Name": "Id", "PhysicalName": "item_id", "DataType": "BIGINT", "IsPK": True}
                    ],
                }
            ],
        }
    }
    out = normalize_catalog(data)
    assert out["name"] == "Inventory"
    assert len(out["entities"]) == 1
    assert out["entities"][0]["physical_name"] == "item"


def test_adapter_output_scores_through_engine():
    """End-to-end: erwin JSON → normalize → engine → ScanResult."""
    import metamart.quality  # noqa: F401  -- register rules
    from metamart.quality.engine import score_catalog
    from metamart.quality.ingest_json import catalog_from_json
    from metamart.quality.pack import default_pack

    erwin_data = {
        "Model": {"Name": "Demo"},
        "Entities": [
            {
                "Name": "Customer",
                "PhysicalName": "customer",
                "Attributes": [
                    {
                        "Name": "Customer ID",
                        "PhysicalName": "customer_id",
                        "DataType": "BIGINT",
                        "IsPK": True,
                        "NotNull": True,
                    }
                ],
            }
        ],
    }
    snapshot = catalog_from_json(erwin_data)
    result = score_catalog(snapshot, default_pack())
    assert result.grade in {"A", "B", "C", "D", "F"}
    assert result.composite_score >= 0
