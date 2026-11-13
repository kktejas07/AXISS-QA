"""The few GitHub API calls Wiseflow makes: check a token, open an issue, comment on a pull request, set a status."""
from __future__ import annotations

import hashlib
import hmac
import re

import httpx

API = "https://api.github.com"
REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


class GitHubError(Exception):
    pass


async def call(token: str, method: str, path: str, body: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.request(method, API + path, headers=headers, json=body)
    except httpx.HTTPError:
        raise GitHubError("GitHub could not be reached. Try again in a moment.")
    if r.status_code == 401:
        raise GitHubError("GitHub did not accept the token. Create a new one and connect again.")
    if r.status_code in (403, 404):
        raise GitHubError("The token cannot reach that repository. Check the repository name and the token's access.")
    if r.status_code >= 400:
        raise GitHubError(f"GitHub refused the request (status {r.status_code}).")
    return r.json() if r.content else {}


async def check(token: str, repo: str | None) -> str:
    """Returns the account the token belongs to; also confirms the repository is reachable when one is named."""
    login = (await call(token, "GET", "/user")).get("login", "")
    if repo:
        await call(token, "GET", f"/repos/{repo}")
    return login


async def create_issue(token: str, repo: str, title: str, body: str) -> tuple[str, str]:
    data = await call(token, "POST", f"/repos/{repo}/issues", {"title": title[:250], "body": body})
    return f"#{data['number']}", data["html_url"]


async def comment(token: str, repo: str, number: int, body: str) -> None:
    await call(token, "POST", f"/repos/{repo}/issues/{number}/comments", {"body": body})


async def set_status(token: str, repo: str, sha: str, state: str, description: str, url: str) -> None:
    await call(token, "POST", f"/repos/{repo}/statuses/{sha}", {"state": state, "description": description[:140], "target_url": url, "context": "Wiseflow"})


def signature_ok(secret: str, payload: bytes, header: str | None) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return bool(header) and hmac.compare_digest(expected, header)
