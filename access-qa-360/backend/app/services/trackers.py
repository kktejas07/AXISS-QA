"""Turning one finding into an issue in GitHub or Linear. (Jira lives in jira.py.)"""
from __future__ import annotations

import html
import json

import httpx

from app.services import github


class TrackerError(Exception):
    pass


def issue_text(finding: dict, app: str, link: str) -> tuple[str, str]:
    title = f"[{str(finding.get('severity', 'medium')).capitalize()}] {finding.get('title', 'Finding')}"
    parts = [finding.get("description") or finding.get("detail") or ""]
    if finding.get("affected_url"):
        parts.append(f"**Where:** {finding['affected_url']}")
    if finding.get("remediation"):
        parts.append(f"**How to fix:** {finding['remediation']}")
    if finding.get("cwe_id"):
        parts.append(f"**Reference:** {finding['cwe_id']}")
    parts.append(f"Found by Wiseflow in {app}. [Open the scan]({link})")
    return title, "\n\n".join(p for p in parts if p)


async def github_issue(token: str, repo: str, finding: dict, app: str, link: str) -> tuple[str, str]:
    title, body = issue_text(finding, app, link)
    try:
        return await github.create_issue(token, repo, title, body)
    except github.GitHubError as e:
        raise TrackerError(str(e))


LINEAR = "https://api.linear.app/graphql"


async def _linear(key: str, query: str, variables: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(LINEAR, headers={"Authorization": key}, json={"query": query, "variables": variables or {}})
    except httpx.HTTPError:
        raise TrackerError("Linear could not be reached. Try again in a moment.")
    if r.status_code in (401, 403):
        raise TrackerError("Linear did not accept the API key. Create a new one and connect again.")
    data = r.json() if r.status_code == 200 else {}
    if r.status_code != 200 or data.get("errors"):
        raise TrackerError("Linear refused the request. Check the team key.")
    return data["data"]


async def linear_team(key: str, team_key: str) -> tuple[str, str]:
    """Returns (team id, team name) for a team key such as "ENG"."""
    data = await _linear(key, "query($k: String!) { teams(filter: {key: {eq: $k}}) { nodes { id name } } }", {"k": team_key})
    nodes = data["teams"]["nodes"]
    if not nodes:
        raise TrackerError(f"No Linear team with the key {team_key} was found.")
    return nodes[0]["id"], nodes[0]["name"]


async def linear_issue(key: str, team_id: str, finding: dict, app: str, link: str) -> tuple[str, str]:
    title, body = issue_text(finding, app, link)
    data = await _linear(
        key, "mutation($i: IssueCreateInput!) { issueCreate(input: $i) { success issue { identifier url } } }",
        {"i": {"teamId": team_id, "title": title[:250], "description": body}},
    )
    issue = data["issueCreate"]["issue"]
    return issue["identifier"], issue["url"]


# ---- Azure Boards -------------------------------------------------------------

AZURE_NAME = r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}"


def _azure_auth(token: str) -> tuple[str, str]:
    return ("", token)      # a personal access token is sent as the password, with an empty user name


async def azure_check(organization: str, project: str, token: str) -> str:
    """Confirms the token can see the project and returns the project's name as Azure spells it."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"https://dev.azure.com/{organization}/_apis/projects/{project}", params={"api-version": "7.0"}, auth=_azure_auth(token))
    except httpx.HTTPError:
        raise TrackerError("Azure DevOps could not be reached. Try again in a moment.")
    # Azure answers a bad token with its sign-in page (status 203), not with 401.
    if r.status_code in (203, 401, 403):
        raise TrackerError("Azure DevOps did not accept the token. Create a new one with Work Items read and write access.")
    if r.status_code == 404:
        raise TrackerError(f"No project called {project} was found in {organization}.")
    if r.status_code != 200:
        raise TrackerError(f"Azure DevOps refused the request (status {r.status_code}).")
    return r.json().get("name", project)


async def azure_issue(organization: str, project: str, kind: str, token: str, finding: dict, app: str, link: str) -> tuple[str, str]:
    title, body = issue_text(finding, app, link)
    patch = [{"op": "add", "path": "/fields/System.Title", "value": title[:250]},
             {"op": "add", "path": "/fields/System.Description", "value": html.escape(body).replace("\n", "<br>")}]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/${kind}", params={"api-version": "7.0"},
                                  auth=_azure_auth(token), content=json.dumps(patch), headers={"Content-Type": "application/json-patch+json"})
    except httpx.HTTPError:
        raise TrackerError("Azure DevOps could not be reached. Try again in a moment.")
    if r.status_code in (203, 401, 403):
        raise TrackerError("Azure DevOps did not accept the token. Connect it again in Settings.")
    if r.status_code >= 400:
        raise TrackerError(f"Azure DevOps refused the request (status {r.status_code}). Check the work item type.")
    data = r.json()
    return f"#{data['id']}", data.get("_links", {}).get("html", {}).get("href") or f"https://dev.azure.com/{organization}/{project}/_workitems/edit/{data['id']}"
