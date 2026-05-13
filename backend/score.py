"""Score a data-model JSON file using the Default rule pack.

Usage:
    python score.py path/to/your_model.json

Prints composite score + per-dimension breakdown + findings to stdout.
No DB required.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import metamart.quality  # noqa: F401  -- registers built-in rules

from metamart.quality.engine import score_catalog
from metamart.quality.ingest_json import catalog_from_json
from metamart.quality.pack import default_pack


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python score.py path/to/model.json", file=sys.stderr)
        return 2

    path = Path(argv[1])
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 2

    try:
        with path.open() as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc}", file=sys.stderr)
        return 2

    try:
        catalog = catalog_from_json(data)
    except (KeyError, ValueError, TypeError) as exc:
        print(f"invalid catalog: {exc}", file=sys.stderr)
        return 2

    result = score_catalog(catalog, default_pack())

    print(f"Model:     {data.get('name', '?')}")
    print(f"Composite: {result.composite_score:6.2f}   Grade: {result.grade}")
    print()
    print("Sub-scores:")
    for s in result.sub_scores:
        print(f"  {s.dimension.value:15s}  {s.score:6.2f}   (population {s.population_size})")
    print()
    print(f"Findings ({len(result.findings)}):")
    by_dim: dict[str, list] = {}
    for f in result.findings:
        by_dim.setdefault(f.dimension.value, []).append(f)
    for dim in sorted(by_dim):
        print(f"  [{dim}]")
        for f in by_dim[dim]:
            print(f"    [{f.severity.value:8s}] {f.message}")
            if f.remediation:
                print(f"               → {f.remediation}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
