from pydantic import BaseModel
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    base_url: str


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_url: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    base_url: str
    owner_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
