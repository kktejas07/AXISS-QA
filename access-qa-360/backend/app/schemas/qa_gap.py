from pydantic import BaseModel
from datetime import datetime


class QAGapOut(BaseModel):
    id: str
    scan_id: str
    route_path: str
    gap_type: str
    risk_level: str
    description: str
    recommendation: str | None
    category: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HeatmapEntry(BaseModel):
    route_path: str
    coverage_status: str
    gap_count: int
    risk_level: str | None


class HeatmapOut(BaseModel):
    scan_id: str
    total_routes: int
    covered: int
    partially_covered: int
    uncovered: int
    entries: list[HeatmapEntry]
