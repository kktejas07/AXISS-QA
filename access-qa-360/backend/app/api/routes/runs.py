from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.run import Run
from app.models.suite import Suite
from app.models.project import Project
from app.models.user import User
from app.schemas.run import RunCreate, RunOut
from app.api.deps import get_current_user
from app.worker.tasks import execute_test_run
from typing import List

router = APIRouter(prefix="/projects/{project_id}/suites/{suite_id}/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=201)
async def trigger_run(project_id: str, suite_id: str, body: RunCreate,
                      db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")
    result = await db.execute(select(Suite).where(Suite.id == suite_id, Suite.project_id == project_id))
    suite = result.scalar_one_or_none()
    if not suite or not suite.generated_code:
        raise HTTPException(400, "Suite not ready — AI generation pending or no code")
    run = Run(suite_id=suite_id, **body.model_dump())
    db.add(run)
    await db.flush()
    execute_test_run.delay(run.id, suite.generated_code)
    return run


@router.get("", response_model=List[RunOut])
async def list_runs(project_id: str, suite_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")
    result = await db.execute(select(Run).where(Run.suite_id == suite_id).order_by(Run.created_at.desc()))
    return result.scalars().all()


@router.get("/{run_id}", response_model=RunOut)
async def get_run(project_id: str, suite_id: str, run_id: str,
                  db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Run).where(Run.id == run_id, Run.suite_id == suite_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    return run
