"""Datatype rules: domain conformance + cross-entity consistency."""
import re
from collections import defaultdict

from metamart.quality.catalog import CatalogSnapshot
from metamart.quality.registry import registry
from metamart.quality.types import Dimension, Finding, Severity

# Heuristic: attributes whose physical names match these patterns should bind
# to a Domain rather than declare a raw type. Substring-match — accepts false
# positives in v1; tighten with rule params later.
DOMAIN_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"email", re.I), "Email"),
    (re.compile(r"(amount|price|cost|total)", re.I), "Money"),
    (re.compile(r"(_at|_ts|timestamp)$", re.I), "Timestamp"),
    (re.compile(r"_date$|^date_", re.I), "Date"),
]


@registry.register(
    rule_id="datatypes.domain_conformance",
    dimension=Dimension.DATATYPES,
    default_severity=Severity.WARN,
)
def domain_conformance(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    findings: list[Finding] = []
    for e in catalog.entities:
        for a in e.attributes:
            for pat, expected in DOMAIN_HINTS:
                if pat.search(a.physical_name) and a.domain_obj_id is None:
                    findings.append(
                        Finding(
                            rule_id="datatypes.domain_conformance",
                            dimension=Dimension.DATATYPES,
                            severity=Severity.WARN,
                            target_obj_id=a.obj_id,
                            message=(
                                f"Attribute '{e.physical_name}.{a.physical_name}' "
                                f"should bind to a '{expected}' domain "
                                f"(raw type: {a.data_type})"
                            ),
                            remediation=f"Bind to the '{expected}' domain",
                        )
                    )
                    break
    return findings


@registry.register(
    rule_id="datatypes.cross_entity_consistency",
    dimension=Dimension.DATATYPES,
    default_severity=Severity.ERROR,
)
def cross_entity_consistency(
    catalog: CatalogSnapshot, params: dict
) -> list[Finding]:
    """Flag attributes sharing a physical_name (case-insensitive) but using
    different data types across entities — usually a copy-paste schema drift bug."""
    by_name: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for e in catalog.entities:
        for a in e.attributes:
            by_name[a.physical_name.lower()].append(
                (a.obj_id, a.data_type.upper(), f"{e.physical_name}.{a.physical_name}")
            )

    findings: list[Finding] = []
    for instances in by_name.values():
        types = {t for _, t, _ in instances}
        if len(types) <= 1:
            continue
        for obj_id, dtype, fqn in instances:
            other_types = sorted(types - {dtype})
            findings.append(
                Finding(
                    rule_id="datatypes.cross_entity_consistency",
                    dimension=Dimension.DATATYPES,
                    severity=Severity.ERROR,
                    target_obj_id=obj_id,
                    message=(
                        f"Attribute '{fqn}' uses '{dtype}' but other entities use {other_types}"
                    ),
                    remediation="Pick one type for all occurrences (or share a Domain)",
                )
            )
    return findings
