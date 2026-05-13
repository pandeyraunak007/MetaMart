"""Quality REST endpoints. v1 ships the stateless `/score-json` utility;
DB-backed scan/snapshot endpoints land in M5."""
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

import metamart.quality  # noqa: F401  -- registers all built-in rules

from metamart.quality.adapters import looks_like_catalog_wrapper
from metamart.quality.engine import score_catalog
from metamart.quality.ingest_json import catalog_from_json
from metamart.quality.pack import default_pack
from metamart.quality.schemas import FindingRead, ScanResultRead, SubScoreRead
from metamart.quality.types import ScanResult

router = APIRouter(prefix="/quality", tags=["quality"])


@router.post("/score-json", response_model=ScanResultRead)
def api_score_json(catalog: Any = Body(...)) -> ScanResultRead:
    """Score a user-supplied catalog using the Default rule pack.

    Accepts either a catalog object or a list. A single-element list whose
    only item looks like a whole-catalog wrapper (e.g. erwin "Save As JSON"
    files) is unwrapped; other lists are treated as a bare entities array.
    """
    catalog = _coerce_to_catalog(catalog)

    try:
        snapshot = catalog_from_json(catalog)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"invalid catalog: {exc}",
        ) from exc

    result = score_catalog(snapshot, default_pack())
    return _to_schema(result)


@router.post("/inspect")
def api_inspect(payload: Any = Body(...)) -> dict[str, Any]:
    """Return a structural fingerprint of any JSON without exposing values.

    Useful for debugging unrecognized formats — paste the output back to
    the team and we'll write a precise adapter without needing your data.
    """
    return {
        "shape": _describe_shape(payload),
        "top_level_type": type(payload).__name__,
        "top_level_keys": (
            list(payload.keys())[:40] if isinstance(payload, dict) else None
        ),
        "list_length": len(payload) if isinstance(payload, list) else None,
    }


# ── helpers ──────────────────────────────────────────────────

def _coerce_to_catalog(catalog: Any) -> Any:
    """Normalize the request body into a dict-shaped catalog.

    - If it's a single-element list whose only item looks like a whole catalog
      wrapper (erwin `{version, Encoding, Description, Objects, ...}` etc.),
      unwrap it.
    - Otherwise, if it's a list, treat as a bare entities array and wrap.
    - If it's neither dict nor list, raise 400.
    """
    if isinstance(catalog, list):
        if (
            len(catalog) >= 1
            and isinstance(catalog[0], dict)
            and looks_like_catalog_wrapper(catalog[0])
        ):
            return catalog[0]
        return {"entities": catalog}
    if not isinstance(catalog, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "body must be a JSON object (a catalog) or a JSON list (entities); "
            f"got {type(catalog).__name__}",
        )
    return catalog


def _describe_shape(data: Any, depth: int = 0, max_depth: int = 5) -> Any:
    """Walk JSON returning keys + type names, never values."""
    if depth >= max_depth:
        return f"<{type(data).__name__} (truncated)>"
    if isinstance(data, dict):
        return {
            k: _describe_shape(v, depth + 1, max_depth)
            for k, v in list(data.items())[:40]
        }
    if isinstance(data, list):
        if not data:
            return "[]"
        sample = _describe_shape(data[0], depth + 1, max_depth)
        return [sample, f"... × {len(data)} items"]
    if isinstance(data, str):
        return f"<str len={len(data)}>"
    if isinstance(data, (int, float, bool)) or data is None:
        return type(data).__name__
    return type(data).__name__


def _to_schema(result: ScanResult) -> ScanResultRead:
    return ScanResultRead(
        pack_id=result.pack_id,
        composite_score=result.composite_score,
        grade=result.grade,
        sub_scores=[
            SubScoreRead(
                dimension=s.dimension.value,
                score=s.score,
                finding_count_by_severity={
                    k.value: v for k, v in s.finding_count_by_severity.items()
                },
                population_size=s.population_size,
            )
            for s in result.sub_scores
        ],
        findings=[
            FindingRead(
                rule_id=f.rule_id,
                dimension=f.dimension.value,
                severity=f.severity.value,
                target_obj_id=f.target_obj_id,
                message=f.message,
                remediation=f.remediation,
            )
            for f in result.findings
        ],
    )
