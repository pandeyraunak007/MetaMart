"""Import-smoke for temporal helpers.

Full SCD2 round-trip tests against a live Postgres land with the integration
harness in M5 once specialization tables (m70_entity, m70_attribute, …) exist
to exercise the helpers end-to-end.
"""
from metamart.mart.temporal import temporal_delete, temporal_upsert


def test_helpers_importable() -> None:
    assert callable(temporal_upsert)
    assert callable(temporal_delete)
