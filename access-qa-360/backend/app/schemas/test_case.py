from pydantic import BaseModel
from datetime import datetime


class TestCaseOut(BaseModel):
    id: str
    scan_id: str
    test_type: str
    title: str
    description: str | None
    preconditions: str | None
    steps: dict | None
    expected_result: str | None
    code_content: str | None
    language: str | None
    status: str
    priority: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TestCaseGenerateRequest(BaseModel):
    test_types: list[str]


class TestCaseExportOut(BaseModel):
    test_case_id: str
    filename: str
    content: str
    language: str | None
