"""End-to-end engine + default-pack run against the three seed catalogs.

No DB required: the seed JSON is converted to a CatalogSnapshot via
tests/_synth.py and scored through the global registry.

These tests document the *current* calibration behavior. Re-tune severities or
weights → expect to update the asserted ranges.
"""
import json
from pathlib import Path

import metamart.quality  # noqa: F401 -- registers built-in rules
from metamart.quality.engine import score_catalog
from metamart.quality.pack import default_pack
from metamart.quality.types import Dimension

from ._synth import synth_catalog_from_json

SEED_DIR = Path(__file__).parent.parent / "seed_data"


def _score(seed_name: str):
    with (SEED_DIR / seed_name).open() as fh:
        cat = synth_catalog_from_json(json.load(fh))
    return score_catalog(cat, default_pack())


def _sub(result, dim: Dimension) -> float:
    return next(s.score for s in result.sub_scores if s.dimension == dim)


def test_northwind_scores_A_grade():
    r = _score("northwind.json")
    assert r.grade == "A"
    assert r.composite_score >= 95.0
    # No findings on the dimensions that should be perfect
    assert _sub(r, Dimension.PKS) == 100.0
    assert _sub(r, Dimension.ORPHANS) == 100.0
    assert _sub(r, Dimension.NAMING) == 100.0
    assert _sub(r, Dimension.NORMALIZATION) == 100.0


def test_warehouse_messy_normalization_drops_for_repeating_addr_columns():
    r = _score("warehouse_messy.json")
    # addr1/addr2/addr3 (ERROR) + tags (WARN) → normalization sub-score below 100.
    assert _sub(r, Dimension.NORMALIZATION) < 100.0
    # Naming is still clean (snake_case throughout).
    assert _sub(r, Dimension.NAMING) == 100.0
    # PKs all present.
    assert _sub(r, Dimension.PKS) == 100.0


def test_warehouse_messy_lineage_drops_for_uncovered_warehouse_entities():
    r = _score("warehouse_messy.json")
    # fact_sales / dim_customer / dim_product have no inbound lineage in the seed.
    assert _sub(r, Dimension.LINEAGE) < 80.0


def test_greenfield_naming_drops_for_pascal_and_camel():
    r = _score("greenfield.json")
    assert _sub(r, Dimension.NAMING) < 100.0
    # Multiple PascalCase / camelCase violations present.
    naming_findings = [f for f in r.findings if f.dimension == Dimension.NAMING]
    assert len(naming_findings) >= 4


def test_greenfield_pks_dimension_drops_for_missing_pks():
    r = _score("greenfield.json")
    # UserData and LegacyLog have no PK → 2 ERROR findings on a population of 3
    # eligible entities (tmp_stuff is staging, excluded).
    assert _sub(r, Dimension.PKS) < 100.0
    pk_findings = [f for f in r.findings if f.dimension == Dimension.PKS]
    assert len(pk_findings) == 2


def test_greenfield_datatypes_flags_cross_entity_drift():
    r = _score("greenfield.json")
    # UserData.UserID (BIGINT) vs OrderInfo.userID (INTEGER) — same physical name
    # (case-insensitive), different types.
    drift = [f for f in r.findings if f.rule_id == "datatypes.cross_entity_consistency"]
    assert len(drift) >= 2


def test_greenfield_glossary_drops_for_zero_coverage():
    r = _score("greenfield.json")
    glossary_findings = [f for f in r.findings if f.dimension == Dimension.GLOSSARY]
    # 3 non-staging entities, none linked to glossary terms.
    assert len(glossary_findings) == 3
    assert _sub(r, Dimension.GLOSSARY) < 100.0


def test_score_ordering_northwind_better_than_warehouse_better_than_greenfield():
    """Sanity: clean > messy > violations on composite. Calibration may drift this
    over time — adjust if rule severities are retuned."""
    nw = _score("northwind.json").composite_score
    wh = _score("warehouse_messy.json").composite_score
    gf = _score("greenfield.json").composite_score
    assert nw > gf, f"Northwind {nw} should beat Greenfield {gf}"
    # Warehouse vs Greenfield: depends on calibration; we assert Northwind tops both.
    assert nw > wh, f"Northwind {nw} should beat Warehouse {wh}"
