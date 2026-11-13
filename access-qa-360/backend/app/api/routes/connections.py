"""An organisation's links to Slack, Microsoft Teams, GitHub and Linear, and the GitHub webhook that scans pull requests."""
import json
import secrets
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrgContext, get_org_context
from app.core.config import settings
from app.core.database import get_db
from app.core.secrets import decrypt, encrypt
from app.models.audit_job import AuditJob
from app.models.integration import Integration
from app.models.organization import Organization
from app.core import providers
from app.services import chatbot_auditor, github, notify, scan_control, schedules, trackers

router = APIRouter(tags=["connections"])
KINDS = ("slack", "teams", "github", "linear", "azure")


async def _row(db: AsyncSession, org_id: str, kind: str) -> Integration | None:
    return (await db.execute(select(Integration).where(Integration.organization_id == org_id, Integration.kind == kind))).scalar_one_or_none()


async def _save(db: AsyncSession, ctx: OrgContext, kind: str, config: dict, secret: str) -> Integration:
    row = await _row(db, ctx.org.id, kind)
    if row:
        row.config, row.secret_encrypted = config, encrypt(secret)
    else:
        row = Integration(organization_id=ctx.org.id, kind=kind, config=config, secret_encrypted=encrypt(secret), created_by=ctx.user.id)
        db.add(row)
    await db.flush()
    return row


def webhook_url(org_id: str) -> str:
    return f"{settings.APP_URL.rstrip('/')}/api/v1/integrations/github/webhook/{org_id}"


def _describe(kind: str, row: Integration | None, org_id: str, can_edit: bool) -> dict:
    if not row:
        return {"connected": False}
    cfg = row.config
    if kind in ("slack", "teams"):
        return {"connected": True, "events": cfg.get("events", "automatic")}
    if kind == "linear":
        return {"connected": True, "team_key": cfg.get("team_key"), "team_name": cfg.get("team_name")}
    if kind == "azure":
        return {"connected": True, **{k: cfg.get(k) for k in ("organization", "project", "work_item_type")}}
    out = {"connected": True, "login": cfg.get("login"), "repo": cfg.get("repo"), "fail_on": cfg.get("fail_on", "high"), "webhook_url": webhook_url(org_id)}
    if can_edit:   # needed to set the webhook up on GitHub; not shown to members and viewers
        out["webhook_secret"] = decrypt(cfg.get("webhook_secret", ""))
    return out


@router.get("/org/connections")
async def list_connections(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    rows = {r.kind: r for r in (await db.execute(select(Integration).where(Integration.organization_id == ctx.org.id))).scalars().all()}
    return {kind: _describe(kind, rows.get(kind), ctx.org.id, ctx.can("org.edit")) for kind in KINDS}


class ChatSave(BaseModel):
    webhook_url: str = Field(min_length=10, max_length=1000)
    # "automatic": scheduled and pull-request scans only. "all": every finished scan.
    events: Literal["automatic", "all"] = "automatic"


@router.put("/org/connections/{kind}")
async def save_connection(kind: Literal["slack", "teams"], body: ChatSave, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("org.edit")
    url = body.webhook_url.strip()
    name = "Slack" if kind == "slack" else "Teams"
    if not notify.chat_url_ok(kind, url):
        raise HTTPException(400, f"That is not a {name} webhook address. Copy it again from {name}.")
    if not await notify.send_chat(kind, url, f"Wiseflow is connected. Scan results for {ctx.org.name} will be posted here."):
        raise HTTPException(400, f"{name} did not accept a test message at that address. Check it and try again.")
    return _describe(kind, await _save(db, ctx, kind, {"events": body.events}, url), ctx.org.id, True)


class GitHubSave(BaseModel):
    token: str = Field(min_length=10, max_length=400)
    repo: str | None = Field(default=None, max_length=210)     # "owner/name": where issues are created
    fail_on: Literal["critical", "high", "never"] = "high"


@router.put("/org/github")
async def save_github(body: GitHubSave, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Connect GitHub with a personal access token. Used to open issues and to report scans on pull requests."""
    ctx.require("org.edit")
    repo = (body.repo or "").strip().removeprefix("https://github.com/").strip("/") or None
    if repo and not github.REPO.match(repo):
        raise HTTPException(422, "Write the repository as owner/name, for example acme/shop")
    try:
        login = await github.check(body.token.strip(), repo)
    except github.GitHubError as e:
        raise HTTPException(400, str(e))
    old = await _row(db, ctx.org.id, "github")
    secret = (old.config.get("webhook_secret") if old else None) or encrypt(secrets.token_hex(24))   # kept when reconnecting
    row = await _save(db, ctx, "github", {"login": login, "repo": repo, "fail_on": body.fail_on, "webhook_secret": secret}, body.token.strip())
    return _describe("github", row, ctx.org.id, True)


class LinearSave(BaseModel):
    api_key: str = Field(min_length=10, max_length=400)
    team_key: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9]+$")


@router.put("/org/linear")
async def save_linear(body: LinearSave, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("org.edit")
    try:
        team_id, team_name = await trackers.linear_team(body.api_key.strip(), body.team_key.upper())
    except trackers.TrackerError as e:
        raise HTTPException(400, str(e))
    row = await _save(db, ctx, "linear", {"team_key": body.team_key.upper(), "team_id": team_id, "team_name": team_name}, body.api_key.strip())
    return _describe("linear", row, ctx.org.id, True)


class AzureSave(BaseModel):
    organization: str = Field(pattern=f"^{trackers.AZURE_NAME}$")
    project: str = Field(pattern=f"^{trackers.AZURE_NAME}$")
    token: str = Field(min_length=10, max_length=400)
    work_item_type: Literal["Bug", "Issue", "Task"] = "Bug"


@router.put("/org/azure")
async def save_azure(body: AzureSave, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Connect Azure Boards with a personal access token, to turn findings into work items."""
    ctx.require("org.edit")
    try:
        project = await trackers.azure_check(body.organization, body.project, body.token.strip())
    except trackers.TrackerError as e:
        raise HTTPException(400, str(e))
    row = await _save(db, ctx, "azure", {"organization": body.organization, "project": project, "work_item_type": body.work_item_type}, body.token.strip())
    return _describe("azure", row, ctx.org.id, True)


# ---- AI settings ---------------------------------------------------------------

class AiSave(BaseModel):
    quality: Literal["fast", "balanced", "best"]
    provider: str = "anthropic"
    # An exact model name, for organisations that want one. Empty: the provider's fast or best model is used.
    model: str | None = Field(default=None, max_length=120)
    # Only for the "custom" provider: where its OpenAI-compatible API lives.
    base_url: str | None = Field(default=None, max_length=500)
    # The organisation's own key. Left out: the saved key, if any, is kept. Empty string: it is removed.
    api_key: str | None = Field(default=None, max_length=400)


def _ai_out(org: Organization) -> dict:
    key = decrypt(org.ai_key_encrypted) if org.ai_key_encrypted else None
    return {
        "quality": org.ai_quality or "balanced", "own_key": bool(key), "key_ending": key[-4:] if key else None,
        "provider": (org.ai_provider or "anthropic") if key else "anthropic", "model": org.ai_model if key else None, "base_url": org.ai_base_url if key else None,
        "providers": [{"id": pid, "name": p["name"], "fast": p["fast"], "best": p["best"]} for pid, p in providers.PROVIDERS.items()],
    }


@router.get("/org/ai")
async def get_ai(ctx: OrgContext = Depends(get_org_context)):
    return _ai_out(ctx.org)


@router.put("/org/ai")
async def save_ai(body: AiSave, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Choose speed against quality for this organisation's AI work, and optionally use its own Anthropic key."""
    ctx.require("org.edit")
    org = ctx.org
    if body.provider not in providers.PROVIDERS:
        raise HTTPException(422, "That AI provider is not one Wiseflow can use")
    removing = body.api_key is not None and not body.api_key.strip()
    key = (body.api_key or "").strip() or (None if removing else decrypt(org.ai_key_encrypted or "") or None)
    org.ai_quality = body.quality
    if removing or not key:
        if body.provider != "anthropic":
            raise HTTPException(422, f"Enter your {providers.PROVIDERS[body.provider]['name']} key. Wiseflow's own key only works with Claude.")
        org.ai_key_encrypted, org.ai_provider, org.ai_model, org.ai_base_url = None, "anthropic", None, None
        await db.flush()
        return _ai_out(org)

    saved_provider = org.ai_provider or "anthropic"
    if body.provider != saved_provider and not (body.api_key or "").strip():
        raise HTTPException(422, "A key only works with the provider it came from. Enter the key for the provider you chose.")
    model = (body.model or "").strip() or None
    base = None
    if body.provider == "anthropic":
        if not (key.startswith("sk-ant-") and len(key) >= 24):
            raise HTTPException(422, "That does not look like an Anthropic API key. They start with sk-ant-")
    else:
        if len(key) < 16:
            raise HTTPException(422, "That key is too short to be an API key")
        if body.provider == "custom":
            base = (body.base_url or "").strip().rstrip("/")
            try:
                chatbot_auditor.check_endpoint(base)      # https, and not an address on a private network
            except chatbot_auditor.ChatbotError:
                raise HTTPException(422, "Enter the API's address starting with https://. Addresses on a private network are not accepted.")
            if not model:
                raise HTTPException(422, "Enter the model name to use with that API")
        # Try the key and the model with one tiny call, so a typo is found now and not in the middle of a scan.
        try:
            await providers.chat(body.provider, base, key, providers.model_for(body.provider, "", body.quality, model),
                                 messages=[{"role": "user", "content": "Reply with the word OK."}], max_tokens=16, timeout=30)
        except providers.ProviderError as e:
            raise HTTPException(400, f"{e}. Check the key and the model name.")
    org.ai_key_encrypted, org.ai_provider, org.ai_model, org.ai_base_url = encrypt(key), body.provider, model, base
    await db.flush()
    return _ai_out(org)


@router.delete("/org/connections/{kind}", status_code=204)
async def disconnect(kind: Literal["slack", "teams", "github", "linear", "azure"], db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("org.edit")
    row = await _row(db, ctx.org.id, kind)
    if row:
        await db.delete(row)


# ---- pull requests ----------------------------------------------------------

@router.post("/integrations/github/webhook/{org_id}")
async def github_webhook(org_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    GitHub calls this when a pull request is opened or gets new commits. The call
    must be signed with the organisation's webhook secret. A scan of the branch
    starts, and its result is posted back on the pull request.
    """
    payload = await request.body()
    row = await _row(db, org_id, "github")
    secret = decrypt(row.config.get("webhook_secret", "")) if row else None
    if not secret or not github.signature_ok(secret, payload, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401, "The signature does not match")
    if request.headers.get("X-GitHub-Event") != "pull_request":
        return {"scan": None, "reason": "Only pull request events start a scan"}
    try:
        event = json.loads(payload)
        pr, action = event["pull_request"], event.get("action")
        base, head = pr["base"]["repo"], pr["head"]["repo"]
        repo, number, sha, branch = base["full_name"], int(pr["number"]), pr["head"]["sha"], pr["head"]["ref"]
        head_name = head["full_name"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "That is not a pull request event")
    if action not in ("opened", "synchronize", "reopened"):
        return {"scan": None, "reason": "Nothing to scan for this event"}
    if not github.REPO.match(repo) or not github.REPO.match(head_name):
        raise HTTPException(400, "That is not a pull request event")

    token = decrypt(row.secret_encrypted)
    link = f"{settings.APP_URL.rstrip('/')}/audits"
    reason = await schedules.blocked(db, await db.get(Organization, org_id))
    if reason:
        if token:
            try:
                await github.set_status(token, repo, sha, "error", reason, link)
            except github.GitHubError:
                pass
        return {"scan": None, "reason": reason}

    now = datetime.now(timezone.utc)
    same_repo = head_name == repo
    job = AuditJob(
        created_by=row.created_by, organization_id=org_id, source_type="repo", repo_url=f"https://github.com/{head_name}.git", repo_ref=branch,
        outputs=["security"], depth="standard", ownership_confirmed_at=now, started_at=now,
        # The token is only ever used on the organisation's own repository, never on a fork.
        trigger={"kind": "pull_request", "repo": repo, "number": number, "sha": sha, "branch": branch, "private": bool(base.get("private")) and same_repo},
    )
    db.add(job)
    await db.commit()
    if token:
        try:
            await github.set_status(token, repo, sha, "pending", "Scanning this branch", f"{link}/{job.id}")
        except github.GitHubError:
            pass
    scan_control.launch(job.id)
    return {"scan": job.id}
