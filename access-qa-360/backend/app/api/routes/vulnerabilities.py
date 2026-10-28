from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.scan import Scan
from app.models.vulnerability import Vulnerability
from app.models.user import User
from app.schemas.vulnerability import VulnerabilityOut, VulnerabilityUpdate
from app.api.deps import get_current_user

router = APIRouter(tags=["vulnerabilities"])


@router.get("/scans/{scan_id}/vulnerabilities", response_model=list[VulnerabilityOut])
async def list_vulnerabilities(
    scan_id: str,
    severity: str | None = None,
    owasp_category: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    if not scan_result.scalar_one_or_none():
        raise HTTPException(404, "Scan not found")

    query = select(Vulnerability).where(Vulnerability.scan_id == scan_id)
    if severity:
        query = query.where(Vulnerability.severity == severity)
    if owasp_category:
        query = query.where(Vulnerability.owasp_category == owasp_category)
    if status:
        query = query.where(Vulnerability.status == status)
    query = query.order_by(Vulnerability.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/vulnerabilities/{vuln_id}", response_model=VulnerabilityOut)
async def get_vulnerability(vuln_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Vulnerability).join(Scan).where(Vulnerability.id == vuln_id, Scan.created_by == user.id)
    )
    vuln = result.scalar_one_or_none()
    if not vuln:
        raise HTTPException(404, "Vulnerability not found")
    return vuln


@router.patch("/vulnerabilities/{vuln_id}", response_model=VulnerabilityOut)
async def update_vulnerability(vuln_id: str, body: VulnerabilityUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Vulnerability).join(Scan).where(Vulnerability.id == vuln_id, Scan.created_by == user.id)
    )
    vuln = result.scalar_one_or_none()
    if not vuln:
        raise HTTPException(404, "Vulnerability not found")
    vuln.status = body.status
    return vuln
