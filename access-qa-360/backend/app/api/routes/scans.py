from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sqlfunc
from app.core.database import get_db
from app.models.scan import Scan
from app.models.vulnerability import Vulnerability, Severity
from app.models.qa_gap import QAGap
from app.models.test_case import TestCase
from app.models.user import User
from app.schemas.scan import ScanCreate, ScanOut, ScanProgress, ScanSummary
from app.api.deps import get_current_user

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("", response_model=ScanOut, status_code=201)
async def create_scan(body: ScanCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    scan = Scan(**body.model_dump(), created_by=user.id)
    db.add(scan)
    await db.flush()
    return scan


@router.get("", response_model=list[ScanOut])
async def list_scans(project_id: str | None = None, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(Scan).where(Scan.created_by == user.id)
    if project_id:
        query = query.where(Scan.project_id == project_id)
    query = query.order_by(Scan.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{scan_id}", response_model=ScanSummary)
async def get_scan(scan_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(404, "Scan not found")

    vuln_result = await db.execute(
        select(sqlfunc.count(Vulnerability.id)).where(Vulnerability.scan_id == scan_id)
    )
    vulnerability_count = vuln_result.scalar() or 0

    critical_result = await db.execute(
        select(sqlfunc.count(Vulnerability.id)).where(Vulnerability.scan_id == scan_id, Vulnerability.severity == Severity.critical)
    )
    critical_count = critical_result.scalar() or 0

    high_result = await db.execute(
        select(sqlfunc.count(Vulnerability.id)).where(Vulnerability.scan_id == scan_id, Vulnerability.severity == Severity.high)
    )
    high_count = high_result.scalar() or 0

    gap_result = await db.execute(
        select(sqlfunc.count(QAGap.id)).where(QAGap.scan_id == scan_id)
    )
    gap_count = gap_result.scalar() or 0

    tc_result = await db.execute(
        select(sqlfunc.count(TestCase.id)).where(TestCase.scan_id == scan_id)
    )
    test_case_count = tc_result.scalar() or 0

    out = ScanSummary.model_validate(scan)
    out.vulnerability_count = vulnerability_count
    out.critical_count = critical_count
    out.high_count = high_count
    out.gap_count = gap_count
    out.test_case_count = test_case_count
    return out


@router.get("/{scan_id}/progress", response_model=ScanProgress)
async def get_scan_progress(scan_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(404, "Scan not found")
    return scan


@router.delete("/{scan_id}", status_code=204)
async def delete_scan(scan_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(404, "Scan not found")
    await db.delete(scan)
