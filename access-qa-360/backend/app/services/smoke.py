"""
A smoke test of a scanned website, run by Wiseflow itself.

Every page the scan mapped is opened again in a real browser and checked: does
it load, does the server answer without an error, does the page's own script
run without crashing. The steps are Wiseflow's own code. The Playwright scripts
written by AI are for people to run in their own pipeline; they are never run here.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.audit_job import AuditJob

MAX_PAGES = 15
_running: dict[str, asyncio.Task] = {}


async def check_pages(urls: list[str], timeout_ms: int = 15000) -> list[dict]:
    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context(ignore_https_errors=True, user_agent="Wiseflow-Smoke/1.0", viewport={"width": 1280, "height": 800})
        for url in urls:
            page = await context.new_page()
            script_errors: list[str] = []
            console_errors: list[str] = []
            broken: list[str] = []
            origin = urlparse(url).netloc
            page.on("pageerror", lambda e: script_errors.append(str(e)[:200]))
            page.on("console", lambda m: console_errors.append(m.text[:200]) if m.type == "error" else None)
            page.on("response", lambda r: broken.append(f"{r.status} {r.url[:160]}") if r.status >= 400 and urlparse(r.url).netloc == origin and r.url.rstrip("/") != url.rstrip("/") else None)
            entry = {"url": url, "path": urlparse(url).path or "/", "status": None, "ms": None, "verdict": "pass", "problems": []}
            started = time.monotonic()
            try:
                response = await page.goto(url, wait_until="load", timeout=timeout_ms)
                await page.wait_for_timeout(400)      # let the page's own script settle
                entry["status"] = response.status if response else None
                entry["ms"] = round((time.monotonic() - started) * 1000)
                if response and response.status >= 400:
                    entry["verdict"] = "fail"
                    entry["problems"].append(f"The server answered with status {response.status}")
                if script_errors:
                    entry["verdict"] = "fail"
                    entry["problems"] += [f"Script error: {e}" for e in script_errors[:3]]
                if broken:
                    entry["verdict"] = "fail" if entry["verdict"] == "fail" else "warn"
                    entry["problems"] += [f"A file the page asks for is missing or failing: {b}" for b in broken[:3]]
                if console_errors and not script_errors:
                    entry["verdict"] = "fail" if entry["verdict"] == "fail" else "warn"
                    entry["problems"] += [f"Console error: {e}" for e in console_errors[:2]]
            except Exception:
                entry.update(verdict="fail", ms=round((time.monotonic() - started) * 1000))
                entry["problems"].append("The page did not load in time")
            finally:
                await page.close()
            results.append(entry)
        await context.close()
        await browser.close()
    return results


async def _save(job_id: str, run: dict) -> None:
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(AuditJob).where(AuditJob.id == job_id))).scalar_one_or_none()
        if job:
            job.tier1_result = {**(job.tier1_result or {}), "smoke_run": run}     # a new dict, so the change is noticed and saved
            await db.commit()


async def _run(job_id: str, urls: list[str]) -> None:
    started = datetime.now(timezone.utc).isoformat()
    try:
        pages = await check_pages(urls)
        count = lambda v: sum(1 for p in pages if p["verdict"] == v)
        await _save(job_id, {"state": "done", "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(), "pages": pages,
                             "passed": count("pass"), "warned": count("warn"), "failed": count("fail")})
    except Exception:
        await _save(job_id, {"state": "failed", "started_at": started, "error": "The smoke test could not be run. Try again."})


def urls_for(job: AuditJob) -> list[str]:
    pages = (job.tier1_result or {}).get("pages") or []
    seen, out = set(), []
    for p in pages:
        url = p.get("url")
        if url and not p.get("error") and url not in seen:
            seen.add(url)
            out.append(url)
    return out[:MAX_PAGES]


def is_running(job_id: str) -> bool:
    return job_id in _running


def start(job_id: str, urls: list[str]) -> None:
    task = asyncio.create_task(_run(job_id, urls))
    _running[job_id] = task
    task.add_done_callback(lambda _: _running.pop(job_id, None))
