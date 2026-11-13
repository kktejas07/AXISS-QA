import asyncio
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.api.routes import auth, projects, suites, runs, webhooks, scans, vulnerabilities, gaps, test_cases, reports, audits, admin, admin_ops, dashboard, org, integrations
from app.api.deps import get_current_user
from app.models.user import User

app = FastAPI(
    title="Wiseflow API",
    description="AI-native QA platform by Wiseflow",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS — reads from env so production just sets CORS_ORIGINS=https://qa.vatax360.com
# ---------------------------------------------------------------------------
_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
# Always allow the production frontend
if "https://qa.vatax360.com" not in _origins:
    _origins.append("https://qa.vatax360.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # lets the web app read download file names
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(suites.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")
app.include_router(vulnerabilities.router, prefix="/api/v1")
app.include_router(gaps.router, prefix="/api/v1")
app.include_router(test_cases.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(audits.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(org.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(admin_ops.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "wiseflow"}


# ---------------------------------------------------------------------------
# SSE — real-time scan progress stream
# ---------------------------------------------------------------------------

@app.get("/api/v1/scans/{scan_id}/stream")
async def stream_scan_progress(
    scan_id: str,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Server-Sent Events stream for real-time scan progress.
    Accepts JWT via ?token= query param (EventSource can't set headers).
    Polls the DB every second and emits progress/status events until
    the scan reaches a terminal state (completed or failed).
    """
    from app.models.scan import Scan, ScanStatus
    from app.core.security import decode_token

    # Auth via query param (SSE limitation)
    user_id = decode_token(token or "") if token else None
    if not user_id:
        raise HTTPException(401, "Unauthorized")

    # Verify ownership
    result = await db.execute(select(Scan).where(Scan.id == scan_id, Scan.created_by == user_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(404, "Scan not found")

    async def _event_generator():
        from app.core.database import AsyncSessionLocal
        terminal = {ScanStatus.completed, ScanStatus.failed}
        last_progress = -1
        last_status = None
        timeout = 600  # 10 minutes max stream
        elapsed = 0

        while elapsed < timeout:
            async with AsyncSessionLocal() as sess:
                r = await sess.execute(select(Scan).where(Scan.id == scan_id))
                s = r.scalar_one_or_none()

            if not s:
                yield f"event: error\ndata: {json.dumps({'message': 'scan not found'})}\n\n"
                break

            if s.progress != last_progress or s.status != last_status:
                last_progress = s.progress
                last_status = s.status
                payload = json.dumps({
                    "scan_id": scan_id,
                    "status": s.status.value,
                    "progress": s.progress,
                })
                yield f"event: progress\ndata: {payload}\n\n"

            if s.status in terminal:
                yield f"event: done\ndata: {json.dumps({'status': s.status.value})}\n\n"
                break

            await asyncio.sleep(1)
            elapsed += 1

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
