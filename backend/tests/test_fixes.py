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


# ── erwin native format-preserving round-trip ────────────────


def _erwin_array_with_violation() -> list:
    """Tiny erwin DM internal flat-array with one snake_case attribute violation."""
    return [
        {"Version": "1.0", "Encoding": "UTF-8", "Description": "erwin Generated JSON"},
        {"O_Id": "1", "O_Type": "1075838978", "Parent_Id": "0", "Name": "M", "Properties": {}},
        # The actual entity (CUSTOMER)
        {"O_Id": "10", "O_Type": "1075838979", "Parent_Id": "1", "Name": "CUSTOMER", "Properties": {}},
        # An attribute whose canonical name has an apostrophe → snake_case violation after slug
        {
            "O_Id": "11",
            "O_Type": "1075838981",
            "Parent_Id": "10",
            "Name": "customer's email",
            "Properties": {
                "1073742126": ["customer's email", "kString"],
                "1075849056": ["varchar", "kString"],
                "1075848978": ["100", "kInteger"],
            },
        },
        # Primary key + member that spells out the attribute name
        {
            "O_Id": "20",
            "O_Type": "1075838985",
            "Parent_Id": "10",
            "Name": "XPKCUSTOMER",
            "Properties": {"1075849004": ["PK", "kString"]},
        },
        {
            "O_Id": "21",
            "O_Type": "1075838986",
            "Parent_Id": "20",
            "Name": "customer's email",
            "Properties": {"1075849017": ["11", "kString"]},
        },
        # Decoy: another object with the SAME O_Id "11" but different O_Type, in
        # a different namespace. erwin actually does this — Alter-Schema /
        # Diagram subtrees reuse O_Ids. The fixer must NOT rename this one.
        {
            "O_Id": "11",
            "O_Type": "1090519048",
            "Parent_Id": "999",
            "Name": "DecoyDoNotTouch",
            "Properties": {"1073742126": ["DecoyDoNotTouch", "kString"]},
        },
    ]


def test_erwin_fix_returns_erwin_shape(client: TestClient) -> None:
    items = _erwin_array_with_violation()
    pre = client.post("/v1/quality/score-json", json=items).json()
    target = next(
        f for f in pre["findings"] if f["rule_id"] == "naming.snake_case_physical"
    )

    fix = client.post(
        "/v1/quality/fix",
        json={
            "catalog": items,
            "rule_id": target["rule_id"],
            "target_obj_id": target["target_obj_id"],
        },
    ).json()

    assert fix["applied"] is True
    # Must come back as a list (erwin shape), not a native dict
    assert isinstance(fix["catalog"], list)
    # Header preserved (erwin signature still recognizable)
    assert "erwin" in fix["catalog"][0]["Description"].lower()
    # Re-scoring the response must succeed
    rescore = client.post("/v1/quality/score-json", json=fix["catalog"]).json()
    assert "grade" in rescore


def test_erwin_fix_updates_name_and_property(client: TestClient) -> None:
    items = _erwin_array_with_violation()
    pre = client.post("/v1/quality/score-json", json=items).json()
    target = next(
        f for f in pre["findings"] if f["rule_id"] == "naming.snake_case_physical"
    )
    fix = client.post(
        "/v1/quality/fix",
        json={
            "catalog": items,
            "rule_id": target["rule_id"],
            "target_obj_id": target["target_obj_id"],
        },
    ).json()
    out = fix["catalog"]

    # The attribute object (O_Type 1075838981, O_Id 11) is renamed in BOTH
    # the top-level Name field and the canonical Property 1073742126.
    attr = next(
        x for x in out
        if isinstance(x, dict)
        and x.get("O_Id") == "11"
        and x.get("O_Type") == "1075838981"
    )
    assert "'" not in attr["Name"]
    assert "'" not in attr["Properties"]["1073742126"][0]
    assert attr["Name"] == attr["Properties"]["1073742126"][0]


def test_erwin_fix_propagates_to_key_member(client: TestClient) -> None:
    items = _erwin_array_with_violation()
    target = next(
        f for f in client.post("/v1/quality/score-json", json=items).json()["findings"]
        if f["rule_id"] == "naming.snake_case_physical"
    )
    out = client.post(
        "/v1/quality/fix",
        json={
            "catalog": items,
            "rule_id": target["rule_id"],
            "target_obj_id": target["target_obj_id"],
        },
    ).json()["catalog"]

    member = next(x for x in out if isinstance(x, dict) and x.get("O_Id") == "21")
    # Member's spelled-out Name should track the attribute rename.
    assert "'" not in member["Name"]


def test_erwin_fix_does_not_touch_decoy_with_same_oid(client: TestClient) -> None:
    """erwin reuses O_Ids across namespaces — the fixer must filter by O_Type."""
    items = _erwin_array_with_violation()
    target = next(
        f for f in client.post("/v1/quality/score-json", json=items).json()["findings"]
        if f["rule_id"] == "naming.snake_case_physical"
    )
    out = client.post(
        "/v1/quality/fix",
        json={
            "catalog": items,
            "rule_id": target["rule_id"],
            "target_obj_id": target["target_obj_id"],
        },
    ).json()["catalog"]

    decoy = next(
        x for x in out
        if isinstance(x, dict)
        and x.get("O_Id") == "11"
        and x.get("O_Type") == "1090519048"
    )
    assert decoy["Name"] == "DecoyDoNotTouch"
    assert decoy["Properties"]["1073742126"][0] == "DecoyDoNotTouch"


def test_erwin_fix_all_is_idempotent(client: TestClient) -> None:
    items = _erwin_array_with_violation()
    first = client.post("/v1/quality/fix-all", json={"catalog": items}).json()
    assert len(first["applied"]) >= 1
    assert isinstance(first["catalog"], list)

    # Re-applying fix-all on the cleaned output should find nothing left.
    second = client.post(
        "/v1/quality/fix-all", json={"catalog": first["catalog"]}
    ).json()
    assert second["applied"] == []
    assert isinstance(second["catalog"], list)


def test_erwin_response_strips_no_provenance_from_list(client: TestClient) -> None:
    """Erwin output is the raw items array — no MetaMart-internal _* keys."""
    items = _erwin_array_with_violation()
    out = client.post("/v1/quality/fix-all", json={"catalog": items}).json()["catalog"]
    for it in out:
        if isinstance(it, dict):
            for k in it:
                assert not k.startswith("_"), f"unexpected internal key {k}"
