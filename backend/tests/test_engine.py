"""End-to-end engine tests against synthetic catalogs (no DB).

Uses a per-test RuleRegistry so we don't depend on (or pollute) the global one.
"""
from metamart.quality.catalog import Attribute, CatalogSnapshot, Entity, Key
from metamart.quality.engine import score_catalog
from metamart.quality.registry import RuleRegistry
from metamart.quality.types import (
    Dimension,
    Finding,
    RuleConfig,
    RulePack,
    Severity,
)


def _entity(
    obj_id: int,
    physical_name: str = "t",
    attrs: list[Attribute] | None = None,
    keys: list[Key] | None = None,
    **kwargs,
) -> Entity:
    return Entity(
        obj_id=obj_id,
        model_obj_id=1,
        logical_name=physical_name.replace("_", " ").title(),
        physical_name=physical_name,
        attributes=attrs or [],
        keys=keys or [],
        **kwargs,
    )


def test_empty_registry_returns_perfect_score() -> None:
    reg = RuleRegistry()
    pack = RulePack(pack_id="empty", name="Empty")
    catalog = CatalogSnapshot(model_obj_id=1, version_id=1, entities=[_entity(10)])

    result = score_catalog(catalog, pack, rule_registry=reg)
    assert result.composite_score == 100.0
    assert result.grade == "A"
    assert result.findings == []


def test_rule_finding_drops_subscore_for_its_dimension() -> None:
    reg = RuleRegistry()

    @reg.register(
        rule_id="missing_pk",
        dimension=Dimension.PKS,
        default_severity=Severity.ERROR,
    )
    def rule(catalog, params):  # noqa: ARG001
        out = []
        for e in catalog.entities:
            if not any(k.key_type == "PK" for k in e.keys):
                out.append(
                    Finding(
                        rule_id="missing_pk",
                        dimension=Dimension.PKS,
                        severity=Severity.ERROR,
                        target_obj_id=e.obj_id,
                        message=f"Entity {e.physical_name} missing PK",
                    )
                )
        return out

    pack = RulePack(pack_id="p", name="Test")
    catalog = CatalogSnapshot(
        model_obj_id=1,
        version_id=1,
        entities=[
            _entity(10, "users"),  # missing PK
            _entity(
                11,
                "orders",
                keys=[Key(obj_id=20, entity_obj_id=11, key_type="PK", name="pk")],
            ),
        ],
    )

    result = score_catalog(catalog, pack, rule_registry=reg)
    pks = next(s for s in result.sub_scores if s.dimension == Dimension.PKS)
    naming = next(s for s in result.sub_scores if s.dimension == Dimension.NAMING)
    assert pks.score < 100.0
    assert naming.score == 100.0  # other dimensions untouched
    assert len(result.findings) == 1
    assert result.findings[0].target_obj_id == 10


def test_rule_disabled_via_pack_config() -> None:
    reg = RuleRegistry()

    @reg.register(rule_id="always_fail", dimension=Dimension.NAMING)
    def rule(catalog, params):  # noqa: ARG001
        return [
            Finding(
                rule_id="always_fail",
                dimension=Dimension.NAMING,
                severity=Severity.ERROR,
                target_obj_id=0,
                message="bad",
            )
        ]

    pack = RulePack(
        pack_id="p",
        name="T",
        rules=[RuleConfig(rule_id="always_fail", enabled=False)],
    )
    catalog = CatalogSnapshot(model_obj_id=1, version_id=1, entities=[_entity(10)])

    result = score_catalog(catalog, pack, rule_registry=reg)
    assert result.findings == []
    assert result.composite_score == 100.0


def test_severity_override_changes_finding_weight() -> None:
    reg = RuleRegistry()

    @reg.register(rule_id="rl", dimension=Dimension.PKS, default_severity=Severity.WARN)
    def rule(catalog, params):  # noqa: ARG001
        return [
            Finding(
                rule_id="rl",
                dimension=Dimension.PKS,
                severity=Severity.WARN,
                target_obj_id=1,
                message="x",
            )
        ]

    cat = CatalogSnapshot(model_obj_id=1, version_id=1, entities=[_entity(1, "users")])

    default_pack = RulePack(pack_id="d", name="Default")
    crit_pack = RulePack(
        pack_id="c",
        name="Critical",
        rules=[RuleConfig(rule_id="rl", severity_override=Severity.CRITICAL)],
    )

    r_default = score_catalog(cat, default_pack, rule_registry=reg)
    r_crit = score_catalog(cat, crit_pack, rule_registry=reg)
    pks_d = next(s for s in r_default.sub_scores if s.dimension == Dimension.PKS).score
    pks_c = next(s for s in r_crit.sub_scores if s.dimension == Dimension.PKS).score
    assert pks_c < pks_d  # critical penalizes harder than warn


def test_geometric_mean_pack_collapses_on_one_zero() -> None:
    reg = RuleRegistry()

    @reg.register(rule_id="kill_pks", dimension=Dimension.PKS, default_severity=Severity.CRITICAL)
    def rule(catalog, params):  # noqa: ARG001
        # produce enough criticals to drive PKs to 0
        return [
            Finding(
                rule_id="kill_pks",
                dimension=Dimension.PKS,
                severity=Severity.CRITICAL,
                target_obj_id=e.obj_id,
                message="x",
            )
            for e in catalog.entities
        ]

    cat = CatalogSnapshot(
        model_obj_id=1,
        version_id=1,
        entities=[_entity(1, "users"), _entity(2, "orders")],
    )

    wa_pack = RulePack(pack_id="wa", name="Avg")
    gm_pack = RulePack(pack_id="gm", name="GeoMean", use_geometric_mean=True)

    wa = score_catalog(cat, wa_pack, rule_registry=reg).composite_score
    gm = score_catalog(cat, gm_pack, rule_registry=reg).composite_score
    assert gm < wa
