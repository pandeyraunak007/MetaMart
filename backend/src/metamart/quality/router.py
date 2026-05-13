"""Quality REST endpoints. v1 ships the stateless `/score-json` utility;
DB-backed scan/snapshot endpoints land in M5."""
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

import metamart.quality  # noqa: F401  -- registers all built-in rules

from metamart.quality.engine import score_catalog
from metamart.quality.ingest_json import catalog_from_json
from metamart.quality.pack import default_pack
from metamart.quality.schemas import FindingRead, ScanResultRead, SubScoreRead
from metamart.quality.types import ScanResult

router = APIRouter(prefix="/quality", tags=["quality"])


@router.post("/score-json", response_model=ScanResultRead)
def api_score_json(catalog: Any = Body(...)) -> ScanResultRead:
    """Score a user-supplied catalog using the Default rule pack.

    Accepts either:
    - a full catalog object `{name, model_type, entities: [...]}`, OR
    - a bare list `[{entity}, {entity}, ...]` (auto-wrapped as
      `{"entities": [...]}` for convenience).

    No DB, no auth. Body shape: see `backend/seed_data/*.json`.
    """
    if isinstance(catalog, list):
        catalog = {"entities": catalog}
    if not isinstance(catalog, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "body must be a JSON object (a catalog) or a JSON list (entities); "
            f"got {type(catalog).__name__}",
        )

    try:
        snapshot = catalog_from_json(catalog)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"invalid catalog: {exc}",
        ) from exc

    result = score_catalog(snapshot, default_pack())
    return _to_schema(result)


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
