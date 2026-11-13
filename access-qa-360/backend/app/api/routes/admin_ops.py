"""
Super admin operations: what is running, what AI is costing, and whether the platform is healthy.

GET  /api/v1/admin/queue               scans running or waiting, and recent failures
POST /api/v1/admin/audits/{id}/stop    stop one
GET  /api/v1/admin/ai-usage            AI calls and estimated cost
GET  /api/v1/admin/health              each dependency, checked now
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.config import settings
from app.core.database import get_db
from app.models.audit_job import AuditJob, AuditStatus
from app.models.integration import AiUsage
from app.models.organization import Organization
from app.models.user import User
from app.services import scan_control
from app.services.mailer import email_configured
from app.services.orgs import log_admin_action

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_super_admin)])

_STEPS = ["Reading the app", "Mobile build", "Security checks", "Test cases", "Report"]


def _value(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _current_step(job: AuditJob) -> str | None:
    for n, name in enumerate(_STEPS, 1):
        if getattr(job, f"tier{n}_status") == "running":
            return name
    return None


def _failure(job: AuditJob) -> str | None:
    for n in range(1, 6):
        result = getattr(job, f"tier{n}_result") or {}
        if getattr(job, f"tier{n}_status") == "failed" and result.get("error"):
            return f"{_STEPS[n - 1]}: {result['error']}"[:300]
    return None


async def _rows(db: AsyncSession, *where, limit: int = 100):
    rows = await db.execute(
        select(AuditJob, User.email, Organization.name)
        .join(User, User.id == AuditJob.created_by)
        .outerjoin(Organization, Organization.id == AuditJob.organization_id)
        .where(*where)
        .order_by(AuditJob.started_at.desc())
        .limit(limit)
    )
    return rows.all()


def _row(job: AuditJob, email: str, org: str | None) -> dict:
    return {
        "id": job.id, "label": job.label, "source_type": job.source_type, "status": _value(job.status), "progress": job.progress,
        "organization": org, "started_by": email, "started_at": job.started_at, "completed_at": job.completed_at,
        "step": _current_step(job), "problem": _failure(job),
        # False for a scan marked running that this server is not actually working on (left over from a restart).
        "alive": scan_control.is_running_here(job.id),
    }


@router.get("/queue")
async def queue(db: AsyncSession = Depends(get_db)):
    active = [AuditStatus.queued, AuditStatus.running]
    running = await _rows(db, AuditJob.status.in_(active), AuditJob.started_at.is_not(None))
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    failed = await _rows(db, AuditJob.status.in_([AuditStatus.failed, AuditStatus.partial]), AuditJob.completed_at >= since, limit=50)
    finished = (
        await db.execute(select(func.count()).select_from(AuditJob).where(AuditJob.status == AuditStatus.completed, AuditJob.completed_at >= since))
    ).scalar() or 0
    return {
        "active": [_row(*r) for r in running],
        "failed_last_24h": [_row(*r) for r in failed],
        "completed_last_24h": finished,
    }


@router.post("/audits/{audit_id}/stop")
async def stop_scan(audit_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_super_admin)):
    job = await db.get(AuditJob, audit_id)
    if not job:
        raise HTTPException(404, "Scan not found")
    try:
        await scan_control.stop(db, job, "Stopped by a Wiseflow administrator")
    except scan_control.NotActive:
        raise HTTPException(409, "This scan is not running")
    await log_admin_action(db, admin, "scan.stop", job.label)
    return {"id": job.id, "status": _value(job.status)}


# ---- AI usage ---------------------------------------------------------------

# US dollars per million tokens (input, output). Estimates only: check your provider's invoice for the real figure.
PRICES = {"claude-sonnet-4-5": (3.0, 15.0), "claude-haiku-4-5": (1.0, 5.0)}


def _cost(model: str, tokens_in: int, tokens_out: int) -> float | None:
    for name, (price_in, price_out) in PRICES.items():
        if model.startswith(name):
            return round(tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out, 4)
    return None


@router.get("/ai-usage")
async def ai_usage(days: int = 30, db: AsyncSession = Depends(get_db)):
    days = max(1, min(days, 365))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await db.execute(select(AiUsage, Organization.name).outerjoin(Organization, Organization.id == AiUsage.organization_id).where(AiUsage.created_at >= since))).all()

    def bucket() -> dict:
        return {"calls": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}

    total, by_model, by_org, by_purpose, by_day = bucket(), {}, {}, {}, {}
    unpriced = set()
    for usage, org_name in rows:
        cost = _cost(usage.model, usage.input_tokens, usage.output_tokens)
        if cost is None and usage.ok:
            unpriced.add(usage.model)
        day = usage.created_at.date().isoformat()
        for group, key in ((by_model, usage.model), (by_org, org_name or "Not tied to an organisation"), (by_purpose, usage.purpose), (by_day, day)):
            for b in (group.setdefault(key, bucket()),):
                b["calls"] += 1
                b["failed"] += 0 if usage.ok else 1
                b["input_tokens"] += usage.input_tokens
                b["output_tokens"] += usage.output_tokens
                b["cost"] = round(b["cost"] + (cost or 0), 4)
        total["calls"] += 1
        total["failed"] += 0 if usage.ok else 1
        total["input_tokens"] += usage.input_tokens
        total["output_tokens"] += usage.output_tokens
        total["cost"] = round(total["cost"] + (cost or 0), 4)

    def listed(group: dict, key: str, by: str = "cost") -> list[dict]:
        return sorted(({key: k, **v} for k, v in group.items()), key=lambda r: (-r[by], r[key]))

    return {
        "days": days,
        "total": total,
        "by_model": listed(by_model, "model"),
        "by_organization": listed(by_org, "organization")[:50],
        "by_purpose": listed(by_purpose, "purpose"),
        "by_day": sorted(({"day": k, **v} for k, v in by_day.items()), key=lambda r: r["day"]),
        "unpriced_models": sorted(unpriced),
        "ai_configured": _ai_key_set(),
    }


# ---- health -----------------------------------------------------------------

def _ai_key_set() -> bool:
    key = (settings.ANTHROPIC_API_KEY or "").strip()
    return len(key) > 20 and not key.endswith("...")


def _check(name: str, ok: bool | None, detail: str, required: bool = True) -> dict:
    """ok None means "not set up", which is fine for optional parts."""
    return {"name": name, "status": "ok" if ok else ("off" if ok is None else "down"), "detail": detail, "required": required}


async def _database(db: AsyncSession) -> dict:
    started = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        version = None
        try:
            version = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        except Exception:
            await db.rollback()
        ms = round((time.perf_counter() - started) * 1000)
        return _check("Database", True, f"Answered in {ms} ms" + (f", schema version {version}" if version else ""))
    except Exception:
        return _check("Database", False, "Not reachable. Nothing in the app can work until it is back.")


def _redis() -> dict:
    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        waiting = client.llen("celery")
        return _check("Queue (Redis)", True, f"Reachable, {waiting} quick scan{'s' if waiting != 1 else ''} waiting")
    except Exception:
        return _check("Queue (Redis)", False, "Not reachable. Quick scans and test runs cannot start.")


def _worker() -> dict:
    try:
        from app.worker.celery_app import celery_app

        replies = celery_app.control.ping(timeout=1.5)
        if replies:
            return _check("Background worker", True, f"{len(replies)} worker{'s' if len(replies) != 1 else ''} answering")
        return _check("Background worker", False, "No worker answered. Quick scans and test runs will wait until one starts.")
    except Exception:
        return _check("Background worker", False, "Cannot be reached, because the queue it listens on is down.")


def _storage() -> dict:
    folder = os.path.abspath(settings.STORAGE_DIR)
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".health")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        free = shutil.disk_usage(folder).free
        gb = free / 1024**3
        return _check("File storage", gb >= 1, f"{gb:.1f} GB free" + ("" if gb >= 1 else ". Uploads and reports will start failing soon."))
    except OSError:
        return _check("File storage", False, "The storage folder cannot be written to. Uploads and reports will fail.")


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    database = await _database(db)
    redis_check, worker, storage = await asyncio.gather(asyncio.to_thread(_redis), asyncio.to_thread(_worker), asyncio.to_thread(_storage))
    checks = [
        database, redis_check, worker, storage,
        _check("AI service key", True if _ai_key_set() else None,
               "A key is set. It is not tested here, to avoid a charge on every page view." if _ai_key_set()
               else "No key set. Scans still run, but test cases, scripts and summaries fall back to basic versions.", required=False),
        _check("Email", True if email_configured() else None,
               f"Sending through {settings.SMTP_HOST}" if email_configured() else "Not set up. Reset links come from a super admin; invite links are copied by hand.", required=False),
        _check("Git", True if shutil.which("git") else False, "Available" if shutil.which("git") else "Not installed. Repository scans cannot run.", required=False),
    ]
    return {
        "healthy": all(c["status"] != "down" for c in checks if c["required"]),
        "checked_at": datetime.now(timezone.utc),
        "environment": settings.ENVIRONMENT,
        "scans_running_here": len(scan_control._tasks),
        "checks": checks,
    }
