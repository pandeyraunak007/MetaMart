"""Smoke tests: app boots and OpenAPI advertises the expected routes.

These do not hit the database — they verify import + routing wiring.
"""
from fastapi.testclient import TestClient

from metamart.main import app


def test_healthz() -> None:
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_advertises_mart_routes() -> None:
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]

    expected = {
        # M1
        "/api/v1/mart/libraries",
        "/api/v1/mart/libraries/{obj_id}",
        # M2
        "/api/v1/mart/users",
        "/api/v1/mart/libraries/{obj_id}/folders",
        "/api/v1/mart/folders",
        "/api/v1/mart/folders/{obj_id}",
        "/api/v1/mart/folders/{obj_id}/children",
        "/api/v1/mart/models",
        "/api/v1/mart/models/{obj_id}",
        "/api/v1/mart/models/{obj_id}/checkout",
        "/api/v1/mart/models/{obj_id}/checkin",
        "/api/v1/mart/models/{obj_id}/versions",
        "/api/v1/mart/permissions",
    }
    missing = expected - paths.keys()
    assert not missing, f"Missing routes: {missing}"
