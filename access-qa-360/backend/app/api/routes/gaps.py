from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.scan import Scan
from app.models.qa_gap import QAGap, GapType
from app.models.user import User
from app.schemas.qa_gap import QAGapOut, HeatmapOut, HeatmapEntry
from app.api.deps import get_current_user

router = APIRouter(tags=["qa-gaps"])


@router.get("/scans/{scan_id}/gaps", response_model=list[QAGapOut])
async def list_gaps(
    scan_id: str,
    gap_type: str | None = None,
    risk_level: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    if not scan_result.scalar_one_or_none():
        raise HTTPException(404, "Scan not found")

    query = select(QAGap).where(QAGap.scan_id == scan_id)
    if gap_type:
        query = query.where(QAGap.gap_type == gap_type)
    if risk_level:
        query = query.where(QAGap.risk_level == risk_level)
    query = query.order_by(QAGap.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/scans/{scan_id}/gaps/heatmap", response_model=HeatmapOut)
async def get_heatmap(scan_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    if not scan_result.scalar_one_or_none():
        raise HTTPException(404, "Scan not found")

    result = await db.execute(select(QAGap).where(QAGap.scan_id == scan_id))
    gaps = result.scalars().all()

    route_map: dict[str, list[QAGap]] = {}
    for gap in gaps:
        route_map.setdefault(gap.route_path, []).append(gap)

    entries = []
    uncovered = 0
    partially = 0
    covered = 0
    for route_path, route_gaps in route_map.items():
        gap_types = {g.gap_type for g in route_gaps}
        if GapType.uncovered in gap_types:
            status = "uncovered"
            uncovered += 1
        elif len(gap_types) > 1:
            status = "partially_covered"
            partially += 1
        else:
            status = "partially_covered"
            partially += 1

        worst_risk = None
        for level in ["critical", "high", "medium", "low"]:
            if any(g.risk_level.value == level for g in route_gaps):
                worst_risk = level
                break

        entries.append(HeatmapEntry(
            route_path=route_path,
            coverage_status=status,
            gap_count=len(route_gaps),
            risk_level=worst_risk,
        ))

    return HeatmapOut(
        scan_id=scan_id,
        total_routes=len(route_map),
        covered=covered,
        partially_covered=partially,
        uncovered=uncovered,
        entries=entries,
    )
