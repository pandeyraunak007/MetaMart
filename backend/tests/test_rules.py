"""Per-rule unit tests. Each test exercises one rule function directly against
a hand-built `CatalogSnapshot` — no DB, no registry, no engine."""
from metamart.quality.catalog import (
    Attribute,
    CatalogSnapshot,
    Entity,
    Key,
    LineageEdge,
    Relationship,
)
from metamart.quality.rules.datatypes import (
    cross_entity_consistency,
    domain_conformance,
)
from metamart.quality.rules.glossary import entity_uncovered
from metamart.quality.rules.lineage import missing_inbound
from metamart.quality.rules.naming import (
    max_length,
    reserved_word,
    snake_case_physical,
)
from metamart.quality.rules.normalization import (
    multi_valued_hint,
    repeating_columns,
)
from metamart.quality.rules.orphans import no_relationships
from metamart.quality.rules.pks import missing_pk
from metamart.quality.types import Severity


def _entity(obj_id, physical, attrs=None, keys=None, **kw):
    return Entity(
        obj_id=obj_id,
        model_obj_id=1,
        logical_name=physical.replace("_", " ").title(),
        physical_name=physical,
        attributes=attrs or [],
        keys=keys or [],
        **kw,
    )


def _attr(obj_id, entity_id, name, dtype="VARCHAR(64)", **kw):
    return Attribute(
        obj_id=obj_id,
        entity_obj_id=entity_id,
        logical_name=name.replace("_", " ").title(),
        physical_name=name,
        data_type=dtype,
        **kw,
    )


# ─── Naming ───────────────────────────────────────────────────

def test_naming_snake_case_flags_pascal_entity():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[_entity(1, "UserData"), _entity(2, "customer")],
    )
    out = snake_case_physical(cat, {})
    assert {f.target_obj_id for f in out} == {1}


def test_naming_snake_case_flags_camel_attribute():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "customer", attrs=[
                _attr(10, 1, "UserID"),
                _attr(11, 1, "name"),
                _attr(12, 1, "orderID"),
            ]),
        ],
    )
    out = snake_case_physical(cat, {})
    assert {f.target_obj_id for f in out} == {10, 12}


def test_naming_max_length_flags_overlong_name():
    long = "a" * 80
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[_entity(1, long)],
    )
    out = max_length(cat, {"max_length": 64})
    assert len(out) == 1
    assert out[0].target_obj_id == 1


def test_naming_reserved_word_flags_table_named_user():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[_entity(1, "user", attrs=[_attr(10, 1, "name")])],
    )
    out = reserved_word(cat, {"reserved": ["user", "select"]})
    assert len(out) == 1
    assert out[0].severity == Severity.ERROR


# ─── PKs ──────────────────────────────────────────────────────

def test_pks_flags_missing_pk_excludes_views_and_staging():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "users"),  # missing PK
            _entity(2, "orders", keys=[Key(obj_id=20, entity_obj_id=2, key_type="PK", name="pk")]),
            _entity(3, "v_active", is_view=True),  # excluded
            _entity(4, "tmp_x", is_staging=True),  # excluded
        ],
    )
    out = missing_pk(cat, {})
    assert {f.target_obj_id for f in out} == {1}


# ─── Orphans ──────────────────────────────────────────────────

def test_orphans_flags_disconnected_entity():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "users"),
            _entity(2, "orders"),
            _entity(3, "audit_log"),  # orphan
            _entity(4, "constants", is_standalone=True),  # excluded
        ],
        fk_relationships=[Relationship(parent_obj_id=1, child_obj_id=2, rel_type="FK")],
    )
    out = no_relationships(cat, {})
    assert {f.target_obj_id for f in out} == {3}


def test_orphans_lineage_edge_counts_as_connection():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[_entity(1, "fact_x"), _entity(2, "src_y")],
        lineage_edges=[LineageEdge(obj_id=100, source_obj_id=2, target_obj_id=1)],
    )
    out = no_relationships(cat, {})
    assert out == []


# ─── Normalization ────────────────────────────────────────────

def test_normalization_repeating_columns_flags_addr_group():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "customer", attrs=[
                _attr(10, 1, "addr1"),
                _attr(11, 1, "addr2"),
                _attr(12, 1, "addr3"),
                _attr(13, 1, "name"),
            ]),
        ],
    )
    out = repeating_columns(cat, {})
    assert len(out) == 1
    assert out[0].severity == Severity.ERROR


def test_normalization_multi_valued_hint_flags_tags_and_tag_list():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "customer", attrs=[
                _attr(10, 1, "tags"),
                _attr(11, 1, "tag_list"),
                _attr(12, 1, "name"),
                _attr(13, 1, "tagList"),
            ]),
        ],
    )
    out = multi_valued_hint(cat, {})
    assert {f.target_obj_id for f in out} == {10, 11, 13}


# ─── Datatypes ────────────────────────────────────────────────

def test_datatypes_domain_conformance_flags_email_without_domain():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "customer", attrs=[
                _attr(10, 1, "email", dtype="VARCHAR(320)"),  # no domain
                _attr(11, 1, "name"),
            ]),
        ],
    )
    out = domain_conformance(cat, {})
    assert {f.target_obj_id for f in out} == {10}


def test_datatypes_domain_conformance_passes_when_domain_bound():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "customer", attrs=[
                _attr(10, 1, "email", dtype="VARCHAR(320)", domain_obj_id=999),
            ]),
        ],
    )
    out = domain_conformance(cat, {})
    assert out == []


def test_datatypes_cross_entity_flags_type_drift():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "users", attrs=[_attr(10, 1, "user_id", dtype="BIGINT")]),
            _entity(2, "orders", attrs=[_attr(20, 2, "user_id", dtype="INTEGER")]),
            _entity(3, "events", attrs=[_attr(30, 3, "user_id", dtype="BIGINT")]),
        ],
    )
    out = cross_entity_consistency(cat, {})
    # All three offenders are reported (the drift is bidirectional information).
    assert {f.target_obj_id for f in out} == {10, 20, 30}
    assert all(f.severity == Severity.ERROR for f in out)


# ─── Glossary ─────────────────────────────────────────────────

def test_glossary_entity_uncovered_flags_missing_link():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "customer", attrs=[]),  # no glossary
            Entity(obj_id=2, model_obj_id=1, logical_name="Order", physical_name="order_h",
                   glossary_term_ids=[42]),  # covered
            _entity(3, "tmp_x", is_staging=True),  # excluded
        ],
    )
    out = entity_uncovered(cat, {})
    assert {f.target_obj_id for f in out} == {1}


# ─── Lineage ──────────────────────────────────────────────────

def test_lineage_flags_warehouse_entity_without_inbound_edge():
    cat = CatalogSnapshot(
        model_obj_id=1, version_id=1,
        entities=[
            _entity(1, "fact_sales"),  # no inbound lineage → flagged
            _entity(2, "dim_customer"),  # has inbound → ok
            _entity(3, "users"),         # not warehouse-style → skipped
        ],
        lineage_edges=[LineageEdge(obj_id=100, source_obj_id=999, target_obj_id=2)],
    )
    out = missing_inbound(cat, {})
    assert {f.target_obj_id for f in out} == {1}
