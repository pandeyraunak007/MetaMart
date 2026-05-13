"""Round-trip tests for the auto-fix endpoints.

For each fixable rule: build a minimal catalog with one violation, fix it
via /quality/fix, re-score, assert the rule no longer flags that target.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _entity(physical: str, attrs: list[dict]) -> dict:
    return {
        "id": f"e_{physical}",
        "logical_name": physical,
        "physical_name": physical,
        "attributes": attrs,
        "keys": [
            {
                "id": f"k_{physical}",
                "name": f"pk_{physical}",
                "key_type": "PK",
                "members": [attrs[0]["id"]],
            }
        ],
    }


def _attr(local_id: str, name: str, position: int = 1) -> dict:
    return {
        "id": local_id,
        "logical_name": name,
        "physical_name": name,
        "data_type": "BIGINT",
        "is_nullable": False,
        "position": position,
    }


def _findings_for(result: dict, rule_id: str) -> list[dict]:
    return [f for f in result["findings"] if f["rule_id"] == rule_id]


# ── snake_case ───────────────────────────────────────────────


def test_fix_snake_case_entity_round_trip(client: TestClient) -> None:
    cat = {
        "name": "Demo",
        "model_type": "physical",
        "entities": [
            _entity("CustomerAccount", [_attr("a1", "customer_id")]),
        ],
    }
    pre = client.post("/v1/quality/score-json", json=cat).json()
    snake = _findings_for(pre, "naming.snake_case_physical")
    assert any(f["target_name"] == "CustomerAccount" for f in snake)

    target = next(f for f in snake if f["target_name"] == "CustomerAccount")
    fix = client.post(
        "/v1/quality/fix",
        json={
            "catalog": cat,
            "rule_id": "naming.snake_case_physical",
            "target_obj_id": target["target_obj_id"],
        },
    ).json()
    assert fix["applied"] is True
    assert fix["catalog"]["entities"][0]["physical_name"] == "customer_account"

    post = _findings_for(fix["result"], "naming.snake_case_physical")
    assert not any(f["target_name"] == "CustomerAccount" for f in post)


def test_fix_snake_case_attribute_round_trip(client: TestClient) -> None:
    cat = {
        "name": "Demo",
        "model_type": "physical",
        "entities": [
            _entity(
                "customer",
                [
                    _attr("a1", "customer_id"),
                    _attr("a2", "FirstName", 2),
                ],
            ),
        ],
    }
    pre = client.post("/v1/quality/score-json", json=cat).json()
    target = next(
        f for f in pre["findings"]
        if f["rule_id"] == "naming.snake_case_physical"
        and f["target_name"] == "customer.FirstName"
    )
    fix = client.post(
        "/v1/quality/fix",
        json={
            "catalog": cat,
            "rule_id": "naming.snake_case_physical",
            "target_obj_id": target["target_obj_id"],
        },
    ).json()
    assert fix["applied"] is True
    assert fix["catalog"]["entities"][0]["attributes"][1]["physical_name"] == "first_name"


# ── reserved word ────────────────────────────────────────────


def test_fix_reserved_word_entity(client: TestClient) -> None:
    cat = {
        "name": "Demo",
        "model_type": "physical",
        "entities": [_entity("user", [_attr("a1", "user_id")])],
    }
    pre = client.post("/v1/quality/score-json", json=cat).json()
    target = next(
        f for f in pre["findings"]
        if f["rule_id"] == "naming.reserved_word" and f["target_name"] == "user"
    )
    fix = client.post(
        "/v1/quality/fix",
        json={
            "catalog": cat,
            "rule_id": "naming.reserved_word",
            "target_obj_id": target["target_obj_id"],
        },
    ).json()
    assert fix["applied"] is True
    assert fix["catalog"]["entities"][0]["physical_name"] == "user_tbl"
    post = _findings_for(fix["result"], "naming.reserved_word")
    assert not any(f["target_name"] == "user" for f in post)


# ── max length ──────────────────────────────────────────────


def test_fix_max_length_entity(client: TestClient) -> None:
    long_name = "a_very_long_physical_name_that_clearly_exceeds_the_default_length_limit_xx"
    cat = {
        "name": "Demo",
        "model_type": "physical",
        "entities": [_entity(long_name, [_attr("a1", "id")])],
    }
    pre = client.post("/v1/quality/score-json", json=cat).json()
    target = next(
        f for f in pre["findings"]
        if f["rule_id"] == "naming.max_length" and f["target_name"] == long_name
    )
    fix = client.post(
        "/v1/quality/fix",
        json={
            "catalog": cat,
            "rule_id": "naming.max_length",
            "target_obj_id": target["target_obj_id"],
        },
    ).json()
    assert fix["applied"] is True
    new_name = fix["catalog"]["entities"][0]["physical_name"]
    assert len(new_name) <= 64
    assert new_name != long_name


# ── /fix-all ─────────────────────────────────────────────────


def test_fix_all_clears_naming_findings(client: TestClient) -> None:
    cat = {
        "name": "Demo",
        "model_type": "physical",
        "entities": [
            _entity(
                "CustomerAccount",
                [
                    _attr("a1", "customer_id"),
                    _attr("a2", "FirstName", 2),
                    _attr("a3", "EMAIL", 3),
                ],
            ),
            _entity("user", [_attr("a4", "user_id")]),
        ],
    }
    res = client.post("/v1/quality/fix-all", json={"catalog": cat}).json()
    assert len(res["applied"]) >= 4
    snake = _findings_for(res["result"], "naming.snake_case_physical")
    reserved = _findings_for(res["result"], "naming.reserved_word")
    assert snake == []
    assert reserved == []


def test_fix_endpoint_404_on_stale_finding(client: TestClient) -> None:
    cat = {
        "name": "Demo",
        "model_type": "physical",
        "entities": [_entity("customer", [_attr("a1", "customer_id")])],
    }
    r = client.post(
        "/v1/quality/fix",
        json={
            "catalog": cat,
            "rule_id": "naming.snake_case_physical",
            "target_obj_id": 99999,
        },
    )
    assert r.status_code == 404


def test_fix_endpoint_400_on_unknown_rule(client: TestClient) -> None:
    cat = {
        "name": "Demo",
        "model_type": "physical",
        "entities": [_entity("customer", [_attr("a1", "customer_id")])],
    }
    r = client.post(
        "/v1/quality/fix",
        json={"catalog": cat, "rule_id": "made.up.rule", "target_obj_id": 100},
    )
    assert r.status_code == 400
