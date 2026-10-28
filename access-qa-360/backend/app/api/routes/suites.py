from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.suite import Suite
from app.models.project import Project
from app.models.user import User
from app.schemas.suite import SuiteCreate, SuiteUpdate, SuiteOut
from app.api.deps import get_current_user
from app.services.ai_generator import generate_test_code
from typing import List

router = APIRouter(prefix="/projects/{project_id}/suites", tags=["suites"])


async def _get_project(project_id: str, user: User, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.post("", response_model=SuiteOut, status_code=201)
async def create_suite(project_id: str, body: SuiteCreate, background_tasks: BackgroundTasks,
                       db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    project = await _get_project(project_id, user, db)
    suite = Suite(**body.model_dump(), project_id=project.id)
    db.add(suite)
    await db.flush()
    background_tasks.add_task(generate_test_code, suite.id, project.base_url, body.feature_description)
    return suite


@router.get("", response_model=List[SuiteOut])
async def list_suites(project_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await _get_project(project_id, user, db)
    result = await db.execute(select(Suite).where(Suite.project_id == project_id))
    return result.scalars().all()


@router.get("/{suite_id}", response_model=SuiteOut)
async def get_suite(project_id: str, suite_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await _get_project(project_id, user, db)
    result = await db.execute(select(Suite).where(Suite.id == suite_id, Suite.project_id == project_id))
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(404, "Suite not found")
    return suite


@router.patch("/{suite_id}", response_model=SuiteOut)
async def update_suite(project_id: str, suite_id: str, body: SuiteUpdate,
                       db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await _get_project(project_id, user, db)
    result = await db.execute(select(Suite).where(Suite.id == suite_id, Suite.project_id == project_id))
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(404, "Suite not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(suite, k, v)
    return suite
