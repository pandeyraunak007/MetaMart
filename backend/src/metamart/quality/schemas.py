"""Pydantic response schemas for quality endpoints."""
from pydantic import BaseModel


class FindingRead(BaseModel):
    rule_id: str
    dimension: str
    severity: str
    target_obj_id: int
    message: str
    remediation: str | None = None


class SubScoreRead(BaseModel):
    dimension: str
    score: float
    finding_count_by_severity: dict[str, int]
    population_size: int


class ScanResultRead(BaseModel):
    pack_id: str
    composite_score: float
    grade: str
    sub_scores: list[SubScoreRead]
    findings: list[FindingRead]
