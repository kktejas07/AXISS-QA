from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.scan import Scan
from app.models.test_case import TestCase
from app.models.user import User
from app.schemas.test_case import TestCaseOut, TestCaseGenerateRequest, TestCaseExportOut
from app.api.deps import get_current_user

router = APIRouter(tags=["test-cases"])


@router.get("/scans/{scan_id}/test-cases", response_model=list[TestCaseOut])
async def list_test_cases(
    scan_id: str,
    test_type: str | None = None,
    priority: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    if not scan_result.scalar_one_or_none():
        raise HTTPException(404, "Scan not found")

    query = select(TestCase).where(TestCase.scan_id == scan_id)
    if test_type:
        query = query.where(TestCase.test_type == test_type)
    if priority:
        query = query.where(TestCase.priority == priority)
    query = query.order_by(TestCase.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/test-cases/{tc_id}", response_model=TestCaseOut)
async def get_test_case(tc_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(TestCase).join(Scan).where(TestCase.id == tc_id, Scan.created_by == user.id)
    )
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(404, "Test case not found")
    return tc


@router.post("/scans/{scan_id}/test-cases/generate", status_code=202)
async def generate_test_cases(
    scan_id: str,
    body: TestCaseGenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user.id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(404, "Scan not found")

    # TODO: Wire to AI test generation service
    return {"message": "Test case generation started", "scan_id": scan_id, "test_types": body.test_types}


@router.post("/test-cases/{tc_id}/export", response_model=TestCaseExportOut)
async def export_test_case(tc_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(TestCase).join(Scan).where(TestCase.id == tc_id, Scan.created_by == user.id)
    )
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(404, "Test case not found")

    ext_map = {"python": ".py", "typescript": ".ts", "javascript": ".js", "gherkin": ".feature", "k6": ".js"}
    ext = ext_map.get(tc.language, ".txt") if tc.language else ".txt"
    filename = f"{tc.test_type}_{tc.id[:8]}{ext}"

    tc.status = "exported"
    return TestCaseExportOut(
        test_case_id=tc.id,
        filename=filename,
        content=tc.code_content or tc.description or "",
        language=tc.language,
    )
