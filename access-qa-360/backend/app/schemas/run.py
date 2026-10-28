from pydantic import BaseModel
from datetime import datetime
from app.models.run import RunStatus


class RunCreate(BaseModel):
    triggered_by: str = "manual"
    branch: str | None = None
    commit_sha: str | None = None


class RunOut(BaseModel):
    id: str
    suite_id: str
    status: RunStatus
    triggered_by: str
    branch: str | None
    commit_sha: str | None
    duration_ms: int | None
    tests_total: int | None
    tests_passed: int | None
    tests_failed: int | None
    error_message: str | None
    triage_summary: str | None
    screenshot_urls: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
