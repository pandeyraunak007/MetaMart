"""Quality REST endpoints. v1 ships the stateless `/score-json` utility;
DB-backed scan/snapshot endpoints land in M5."""
from typing import Any

from fastapi import APIRouter, HTTPException, status

import metamart.quality  # noqa: F401  -- registers all built-in rules

from metamart.quality.engine import score_catalog
from metamart.quality.ingest_json import catalog_from_json
from metamart.quality.pack import default_pack
from metamart.quality.schemas import FindingRead, ScanResultRead, SubScoreRead
from metamart.quality.types import ScanResult

router = APIRouter(prefix="/quality", tags=["quality"])


@router.post("/score-json", response_model=ScanResultRead)
def api_score_json(catalog: dict[str, Any]) -> ScanResultRead:
    """Score a user-supplied catalog JSON using the Default rule pack.

    No DB write, no auth. Body shape: same as `backend/seed_data/*.json`.
    """
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
