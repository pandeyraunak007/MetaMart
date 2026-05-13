"""Smoke tests for `POST /api/v1/quality/score-json`."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from metamart.main import app

SEED_DIR = Path(__file__).parent.parent / "seed_data"


def test_score_json_returns_grade_for_clean_catalog() -> None:
    with (SEED_DIR / "northwind.json").open() as fh:
        catalog = json.load(fh)

    client = TestClient(app)
    resp = client.post("/api/v1/quality/score-json", json=catalog)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["grade"] == "A"
    assert body["composite_score"] >= 95.0
    assert body["pack_id"] == "default"
    assert len(body["sub_scores"]) == 7
    dims = {s["dimension"] for s in body["sub_scores"]}
    assert dims == {
        "naming",
        "normalization",
        "orphans",
        "pks",
        "datatypes",
        "glossary",
        "lineage",
    }


def test_score_json_finds_issues_in_messy_catalog() -> None:
    with (SEED_DIR / "greenfield.json").open() as fh:
        catalog = json.load(fh)

    client = TestClient(app)
    resp = client.post("/api/v1/quality/score-json", json=catalog)
    assert resp.status_code == 200

    body = resp.json()
    findings = body["findings"]
    rule_ids = {f["rule_id"] for f in findings}
    # Some flavor of these violations should fire on the greenfield seed.
    assert "pks.missing_pk" in rule_ids
    assert "naming.snake_case_physical" in rule_ids
    assert "datatypes.cross_entity_consistency" in rule_ids


def test_score_json_rejects_missing_required_keys() -> None:
    client = TestClient(app)
    resp = client.post("/api/v1/quality/score-json", json={"description": "nope"})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    # Error response now includes a structural fingerprint alongside the message.
    assert isinstance(detail, dict)
    assert "message" in detail
    assert "entities" in detail["message"].lower()
    assert "shape" in detail


def test_score_json_rejects_non_object_body() -> None:
    client = TestClient(app)
    # Lists / scalars must be rejected as invalid catalogs.
    resp = client.post("/api/v1/quality/score-json", json=["entity_list"])
    assert resp.status_code in (400, 422)


def test_score_json_unwraps_list_around_erwin_wrapper() -> None:
    """erwin's exporter sometimes wraps the whole catalog in a single-element list.
    The router should detect a catalog-wrapper-shaped first element and unwrap it
    instead of treating it as a single entity."""
    erwin_wrapped_in_list = [
        {
            "version": "1.0",
            "Encoding": "UTF-8",
            "Description": "erwin Generated JSON File",
            "Objects": {
                "Entity": [
                    {
                        "Name": "Customer",
                        "Physical_Name": "Customer",
                        "Attributes": {
                            "Attribute": [
                                {
                                    "Name": "CustomerId",
                                    "Physical_Name": "CustomerId",
                                    "Physical_Data_Type": "INT",
                                    "Null_Option": "NOT NULL",
                                    "Key_Type": "PRIMARY KEY",
                                }
                            ]
                        },
                    }
                ]
            },
        }
    ]

    client = TestClient(app)
    resp = client.post("/api/v1/quality/score-json", json=erwin_wrapped_in_list)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["grade"] in {"A", "B", "C", "D", "F"}
    assert isinstance(body["sub_scores"], list)


def test_inspect_returns_shape_without_values() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/v1/quality/inspect",
        json={
            "version": "1.0",
            "Description": "Some sensitive description",
            "Objects": {"Entity": [{"Name": "Customer"}]},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["top_level_type"] == "dict"
    assert "version" in body["top_level_keys"]
    assert "Description" in body["top_level_keys"]
    # Values are summarised, not echoed.
    shape = body["shape"]
    assert "str len=" in shape["Description"]
