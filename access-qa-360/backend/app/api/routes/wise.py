"""Wise (the assistant), the documents it answers from, and the ready-made presets and test packs."""
import csv
import io
import os
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrgContext, get_org_context
from app.core.database import get_db
from app.models.wise import WiseDocument
from app.services import presets, wise

router = APIRouter(tags=["wise"])
MAX_DOC_BYTES = 1024 * 1024
MAX_DOCS = 50
DOC_TYPES = (".txt", ".md", ".csv", ".json", ".feature")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatIn(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=30)
    # The scan the person is looking at, so it is always among the things searched.
    audit_id: str | None = None


@router.post("/wise/chat")
async def chat(body: ChatIn, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Answer a question from the organisation's own scans and documents. Wise reads; it never changes anything."""
    if body.messages[-1].role != "user":
        raise HTTPException(422, "The last message must be the question")
    return await wise.answer(db, ctx.org.id, ctx.user.id, [m.model_dump() for m in body.messages], body.audit_id)


@router.get("/wise/prompts")
async def prompts():
    return wise.PROMPTS


class DocumentOut(BaseModel):
    id: str
    name: str
    size: int
    created_at: datetime


def _out(doc: WiseDocument) -> DocumentOut:
    return DocumentOut(id=doc.id, name=doc.name, size=len(doc.content), created_at=doc.created_at)


@router.get("/wise/documents", response_model=list[DocumentOut])
async def list_documents(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    rows = (await db.execute(select(WiseDocument).where(WiseDocument.organization_id == ctx.org.id).order_by(WiseDocument.created_at.desc()))).scalars().all()
    return [_out(d) for d in rows]


@router.post("/wise/documents", response_model=DocumentOut, status_code=201)
async def add_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Add a text document (requirements, user stories, release notes) for Wise to answer from."""
    ctx.require("org.edit")
    name = os.path.basename(file.filename or "")[:255]
    if os.path.splitext(name)[1].lower() not in DOC_TYPES:
        raise HTTPException(415, f"Upload a text file: {', '.join(DOC_TYPES)}")
    raw = await file.read(MAX_DOC_BYTES + 1)
    if len(raw) > MAX_DOC_BYTES:
        raise HTTPException(413, "That file is larger than 1 MB")
    try:
        text = raw.decode("utf-8-sig").replace("\x00", "").strip()
    except UnicodeDecodeError:
        raise HTTPException(415, "That file is not plain text")
    if not text:
        raise HTTPException(400, "The file is empty")
    count = (await db.execute(select(func.count()).select_from(WiseDocument).where(WiseDocument.organization_id == ctx.org.id))).scalar_one()
    if count >= MAX_DOCS:
        raise HTTPException(400, f"An organisation can keep {MAX_DOCS} documents. Remove one to add another.")
    doc = WiseDocument(organization_id=ctx.org.id, name=name, content=text, created_by=ctx.user.id)
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return _out(doc)


@router.delete("/wise/documents/{doc_id}", status_code=204)
async def remove_document(doc_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("org.edit")
    doc = (await db.execute(select(WiseDocument).where(WiseDocument.id == doc_id, WiseDocument.organization_id == ctx.org.id))).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    await db.delete(doc)


# ---- ready-made presets and packs --------------------------------------------

@router.get("/library")
async def library(_: OrgContext = Depends(get_org_context)):
    return {"scan_presets": presets.SCAN_PRESETS, "test_packs": presets.TEST_PACKS}


@router.get("/library/test-packs/{pack_id}.csv")
async def pack_csv(pack_id: str, _: OrgContext = Depends(get_org_context)):
    pack = presets.pack(pack_id)
    if not pack:
        raise HTTPException(404, "That test pack does not exist")
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["ID", "Title", "Category", "Priority", "Steps", "Expected result"])
    for c in pack["cases"]:
        writer.writerow([c["id"], c["title"], c["category"], c["priority"], "\n".join(f"{i}. {s}" for i, s in enumerate(c["steps"], 1)), c["expected_result"]])
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="wiseflow-{pack_id}-test-cases.csv"'})
