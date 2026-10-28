from pydantic import BaseModel
from datetime import datetime


class ReportCreate(BaseModel):
    report_type: str
    format: str = "pdf"


class ReportOut(BaseModel):
    id: str
    scan_id: str
    report_type: str
    format: str
    file_path: str | None
    generated_at: datetime

    model_config = {"from_attributes": True}
