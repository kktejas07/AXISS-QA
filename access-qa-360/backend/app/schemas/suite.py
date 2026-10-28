from pydantic import BaseModel
from datetime import datetime
from app.models.suite import SuiteStatus


class SuiteCreate(BaseModel):
    name: str
    description: str | None = None
    feature_description: str


class SuiteUpdate(BaseModel):
    name: str | None = None
    feature_description: str | None = None
    generated_code: str | None = None
    status: SuiteStatus | None = None


class SuiteOut(BaseModel):
    id: str
    name: str
    description: str | None
    feature_description: str
    generated_code: str | None
    status: SuiteStatus
    project_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
