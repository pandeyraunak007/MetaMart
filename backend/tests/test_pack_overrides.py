"""Tests for the rules-listing endpoint and pack overrides on score/fix.

The pack overrides path is what backs the frontend's Rules editor: users
configure per-rule enable / severity / params and every score call sends
the resulting overrides along.
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


# ── /quality/rules ────────────────────────────────────────────


def test_rules_endpoint_lists_every_registered_rule(client: TestClient) -> None:
    r = client.get("/v1/quality/rules")
    assert r.status_code == 200
    body = r.json()
    rule_ids = {r["rule_id"] for r in body["rules"]}
    # Spot-check a representative selection across dimensions
    assert "naming.snake_case_physical" in rule_ids
    assert "naming.max_length" in rule_ids
    assert "pks.missing_pk" in rule_ids
    assert "datatypes.cross_entity_consistency" in rule_ids
    assert "glossary.entity_uncovered" in rule_ids


def test_rules_endpoint_includes_dimension_severity_and_fixer_flag(
    client: TestClient,
) -> None:
    body = client.get("/v1/quality/rules").json()
    by_id = {r["rule_id"]: r for r in body["rules"]}

    snake = by_id["naming.snake_case_physical"]
    assert snake["dimension"] == "naming"
    assert snake["default_severity"] == "warn"
    assert snake["has_fixer"] is True

    pks = by_id["pks.missing_pk"]
    assert pks["dimension"] == "pks"
    assert pks["default_severity"] == "error"
    # No auto-fix today for missing PKs
    assert pks["has_fixer"] is False


def test_rules_endpoint_returns_default_params(client: TestClient) -> None:
    body = client.get("/v1/quality/rules").json()
    by_id = {r["rule_id"]: r for r in body["rules"]}
    assert by_id["naming.max_length"]["default_params"] == {"max_length": 64}


# ── /score-json with pack overrides ───────────────────────────


def _bad_naming_catalog() -> dict:
    return {
        "name": "Demo",
        "model_type": "physical",
        "entities": [
            _entity("CustomerAccount", [_attr("a1", "customer_id")]),
        ],
    }


def test_score_envelope_shape_uses_default_pack_when_no_overrides(
    client: TestClient,
) -> None:
    body = {"catalog": _bad_naming_catalog()}
    out = client.post("/v1/quality/score-json", json=body).json()
    snake = [f for f in out["findings"] if f["rule_id"] == "naming.snake_case_physical"]
    assert any(f["target_name"] == "CustomerAccount" for f in snake)


def test_score_disabled_rule_drops_its_findings(client: TestClient) -> None:
    body = {
        "catalog": _bad_naming_catalog(),
        "pack_overrides": {
            "rules": [{"rule_id": "naming.snake_case_physical", "enabled": False}],
        },
    }
    out = client.post("/v1/quality/score-json", json=body).json()
    assert all(
        f["rule_id"] != "naming.snake_case_physical" for f in out["findings"]
    ), "disabled rule should produce no findings"


def test_score_severity_override_applies_to_findings(client: TestClient) -> None:
    body = {
        "catalog": _bad_naming_catalog(),
        "pack_overrides": {
            "rules": [
                {
                    "rule_id": "naming.snake_case_physical",
                    "severity_override": "error",
                }
            ],
        },
    }
    out = client.post("/v1/quality/score-json", json=body).json()
    snake = [f for f in out["findings"] if f["rule_id"] == "naming.snake_case_physical"]
    assert snake, "expected at least one snake_case finding"
    assert all(f["severity"] == "error" for f in snake)


def test_score_params_override_changes_threshold(client: TestClient) -> None:
    cat = {
        "name": "Demo",
        "model_type": "physical",
        # 30-char snake_case name — passes default max_length (64) but fails
        # under a tighter override.
        "entities": [
            _entity(
                "an_attribute_thirty_chars_long",
                [_attr("a1", "id")],
            ),
        ],
    }
    # Default pack: no max_length finding for this name.
    default_out = client.post("/v1/quality/score-json", json=cat).json()
    assert all(f["rule_id"] != "naming.max_length" for f in default_out["findings"])

    # Tighter override: max_length 20 → name (30 chars) now violates.
    body = {
        "catalog": cat,
        "pack_overrides": {
            "rules": [
                {
                    "rule_id": "naming.max_length",
                    "params_override": {"max_length": 20},
                }
            ],
        },
    }
    custom_out = client.post("/v1/quality/score-json", json=body).json()
    assert any(
        f["rule_id"] == "naming.max_length"
        and f["target_name"] == "an_attribute_thirty_chars_long"
        for f in custom_out["findings"]
    )


def test_score_unknown_rule_id_in_overrides_is_ignored(client: TestClient) -> None:
    """Old packs in client localStorage shouldn't fail scoring after a rename."""
    body = {
        "catalog": _bad_naming_catalog(),
        "pack_overrides": {
            "rules": [{"rule_id": "made.up.rule_that_does_not_exist", "enabled": False}],
        },
    }
    r = client.post("/v1/quality/score-json", json=body)
    assert r.status_code == 200
    # Still scores normally — the unknown override is silently dropped
    snake = [f for f in r.json()["findings"] if f["rule_id"] == "naming.snake_case_physical"]
    assert snake


def test_score_invalid_severity_override_is_400(client: TestClient) -> None:
    body = {
        "catalog": _bad_naming_catalog(),
        "pack_overrides": {
            "rules": [
                {
                    "rule_id": "naming.snake_case_physical",
                    "severity_override": "ULTRA_CRITICAL",
                }
            ],
        },
    }
    r = client.post("/v1/quality/score-json", json=body)
    assert r.status_code == 400


# ── /fix and /fix-all honor the active pack ──────────────────


def test_fix_endpoint_respects_disabled_rules_in_postfix_score(client: TestClient) -> None:
    """Re-score after a fix should use the same pack the user just configured."""
    cat = _bad_naming_catalog()
    pre = client.post("/v1/quality/score-json", json=cat).json()
    sc = next(f for f in pre["findings"] if f["rule_id"] == "naming.snake_case_physical")

    fix = client.post(
        "/v1/quality/fix",
        json={
            "catalog": cat,
            "rule_id": "naming.snake_case_physical",
            "target_obj_id": sc["target_obj_id"],
            "pack_overrides": {
                # User has disabled the glossary rule; fix should re-score
                # without it firing in the post-fix result.
                "rules": [{"rule_id": "glossary.entity_uncovered", "enabled": False}],
            },
        },
    ).json()
    assert fix["applied"] is True
    assert all(
        f["rule_id"] != "glossary.entity_uncovered" for f in fix["result"]["findings"]
    )


def test_fix_all_respects_pack_overrides(client: TestClient) -> None:
    cat = {
        "name": "Demo",
        "model_type": "physical",
        "entities": [
            _entity(
                "CustomerAccount",
                [_attr("a1", "customer_id"), _attr("a2", "FirstName", 2)],
            ),
        ],
    }
    res = client.post(
        "/v1/quality/fix-all",
        json={
            "catalog": cat,
            "pack_overrides": {
                # Disable the snake_case rule itself: nothing should be fixed.
                "rules": [{"rule_id": "naming.snake_case_physical", "enabled": False}],
            },
        },
    ).json()
    assert res["applied"] == [], (
        "fix-all should be a no-op when the only fixable rule is disabled"
    )
