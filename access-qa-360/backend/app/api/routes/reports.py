from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.scan import Scan
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportCreate, ReportOut
from app.api.deps import get_current_user
import os

router = APIRouter(tags=["reports"])


@router.post("/scans/{scan_id}/reports", response_model=ReportOut, status_code=201)
async def create_report(
    scan_id: str,
    body: ReportCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(404, "Scan not found")

    report = Report(
        scan_id=scan_id,
        report_type=body.report_type,
        format=body.format,
    )
    db.add(report)
    await db.flush()
    # TODO: Wire to report generation service (PDF/DOCX/JSON/CSV)
    return report


@router.get("/scans/{scan_id}/reports", response_model=list[ReportOut])
async def list_reports(scan_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    if not scan_result.scalar_one_or_none():
        raise HTTPException(404, "Scan not found")

    result = await db.execute(
        select(Report).where(Report.scan_id == scan_id).order_by(Report.generated_at.desc())
    )
    return result.scalars().all()


@router.get("/reports/{report_id}/download")
async def download_report(report_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Report).join(Scan).where(Report.id == report_id, Scan.created_by == user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, "Report not found")
    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(404, "Report file not yet generated")

    media_types = {"pdf": "application/pdf", "json": "application/json", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "csv": "text/csv"}
    return FileResponse(report.file_path, media_type=media_types.get(report.format, "application/octet-stream"))
