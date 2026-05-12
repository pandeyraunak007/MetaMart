"""Smoke checks for the JSON catalog ingest path."""
import json
from pathlib import Path

from metamart.mart.ingest import ingest_catalog

SEED_DIR = Path(__file__).parent.parent / "seed_data"


def test_ingest_callable() -> None:
    assert callable(ingest_catalog)


def test_seed_files_present_and_well_formed() -> None:
    expected = ["northwind.json", "warehouse_messy.json", "greenfield.json"]
    for fname in expected:
        p = SEED_DIR / fname
        assert p.exists(), f"missing seed file: {p}"
        with p.open() as fh:
            catalog = json.load(fh)
        assert isinstance(catalog.get("name"), str) and catalog["name"]
        assert catalog.get("model_type") in {"logical", "physical", "lp"}
        assert isinstance(catalog.get("entities", []), list)


def test_seed_attribute_references_resolve_locally() -> None:
    """Every key 'members' id and relationship parent/child id must exist in the catalog."""
    for fname in ["northwind.json", "warehouse_messy.json", "greenfield.json"]:
        with (SEED_DIR / fname).open() as fh:
            catalog = json.load(fh)
        local_ids: set[str] = set()
        for sa in catalog.get("subject_areas", []):
            local_ids.add(sa["id"])
        for d in catalog.get("domains", []):
            local_ids.add(d["id"])
        for g in catalog.get("glossary", []):
            local_ids.add(g["id"])
        for e in catalog.get("entities", []):
            local_ids.add(e["id"])
            for a in e.get("attributes", []):
                local_ids.add(a["id"])
            for k in e.get("keys", []):
                local_ids.add(k["id"])

        # Key members must reference an attribute defined in the same entity.
        for e in catalog.get("entities", []):
            entity_attr_ids = {a["id"] for a in e.get("attributes", [])}
            for k in e.get("keys", []):
                for m in k["members"]:
                    assert m in entity_attr_ids, f"{fname}: key '{k['id']}' references unknown attr '{m}'"

        # Relationships must reference defined entities.
        entity_ids = {e["id"] for e in catalog.get("entities", [])}
        for r in catalog.get("relationships", []):
            assert r["parent"] in entity_ids, f"{fname}: rel '{r['id']}' parent missing"
            assert r["child"] in entity_ids, f"{fname}: rel '{r['id']}' child missing"
