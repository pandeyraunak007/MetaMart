"""Normalization heuristics: 1NF repeating columns and multi-valued column hints."""
import re

from metamart.quality.catalog import CatalogSnapshot
from metamart.quality.registry import registry
from metamart.quality.types import Dimension, Finding, Severity

# Detects names like addr1/addr2/addr3 (a stem followed by a trailing digit).
REPEATING_SUFFIX_RE = re.compile(r"^(.+?)_?(\d+)$")

# Heuristic patterns that suggest multi-valued data crammed into a single column.
MULTI_VALUED_PATTERNS = [
    re.compile(r"^tags?$", re.I),         # tag, tags
    re.compile(r".*_list$", re.I),        # *_list
    re.compile(r".*[a-z]List$"),          # PascalCase: tagList, itemList
    re.compile(r"^list_.*$", re.I),       # list_*
    re.compile(r".*_csv$", re.I),         # *_csv
]


@registry.register(
    rule_id="normalization.repeating_columns",
    dimension=Dimension.NORMALIZATION,
    default_severity=Severity.ERROR,
)
def repeating_columns(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    findings: list[Finding] = []
    for e in catalog.entities:
        stems: dict[str, list[str]] = {}
        for a in e.attributes:
            m = REPEATING_SUFFIX_RE.match(a.physical_name)
            if m:
                stem = m.group(1).rstrip("_")
                stems.setdefault(stem, []).append(a.physical_name)
        for stem, names in stems.items():
            if len(names) >= 2:
                findings.append(
                    Finding(
                        rule_id="normalization.repeating_columns",
                        dimension=Dimension.NORMALIZATION,
                        severity=Severity.ERROR,
                        target_obj_id=e.obj_id,
                        message=(
                            f"Entity '{e.physical_name}' has repeating columns "
                            f"{sorted(names)} (1NF concern)"
                        ),
                        remediation=f"Extract '{stem}' into a child entity",
                    )
                )
    return findings


@registry.register(
    rule_id="normalization.multi_valued_hint",
    dimension=Dimension.NORMALIZATION,
    default_severity=Severity.WARN,
)
def multi_valued_hint(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    findings: list[Finding] = []
    for e in catalog.entities:
        for a in e.attributes:
            for pat in MULTI_VALUED_PATTERNS:
                if pat.match(a.physical_name):
                    findings.append(
                        Finding(
                            rule_id="normalization.multi_valued_hint",
                            dimension=Dimension.NORMALIZATION,
                            severity=Severity.WARN,
                            target_obj_id=a.obj_id,
                            message=(
                                f"Attribute '{e.physical_name}.{a.physical_name}' "
                                f"looks multi-valued (1NF concern)"
                            ),
                            remediation="Extract values into a child entity",
                        )
                    )
                    break
    return findings
