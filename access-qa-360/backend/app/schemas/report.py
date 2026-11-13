from pydantic import BaseModel
from datetime import datetime


from pydantic import field_validator

# Names the web app has always sent, mapped to the stored ones.
_TYPE_ALIASES = {"executive": "executive_summary", "qa-gap": "qa_gap", "test-bundle": "test_bundle"}
_FORMATS = {"pdf", "json", "csv"}


class ReportCreate(BaseModel):
    report_type: str
    format: str = "pdf"

    @field_validator("report_type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        v = _TYPE_ALIASES.get(v, v)
        if v not in {"executive_summary", "vulnerability", "qa_gap", "test_bundle", "compliance", "diff"}:
            raise ValueError("Unknown report type")
        return v

    @field_validator("format")
    @classmethod
    def _known_format(cls, v: str) -> str:
        if v not in _FORMATS:
            raise ValueError("Reports can be PDF, JSON or CSV")
        return v


class ReportOut(BaseModel):
    id: str
    scan_id: str
    report_type: str
    format: str
    file_path: str | None
    generated_at: datetime
    created_at: datetime
    # "generating" until the file exists, then "ready"
    status: str
    download_url: str | None

    model_config = {"from_attributes": True}
