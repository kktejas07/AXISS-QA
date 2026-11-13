"""Turning one finding into an issue in GitHub or Linear. (Jira lives in jira.py.)"""
from __future__ import annotations

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
