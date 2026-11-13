"""Jira Cloud: check a connection and create issues from findings."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx


class JiraError(Exception):
    """A problem the user can act on, in plain words."""


_HOST = re.compile(r"^[a-z0-9][a-z0-9-]*\.atlassian\.net$")
_SEVERITY_LABEL = {"critical": "severity-critical", "high": "severity-high", "medium": "severity-medium", "low": "severity-low"}


def clean_base_url(value: str) -> str:
    """Only Jira Cloud sites are accepted, so the server never calls an address of the user's choosing."""
    parsed = urlparse((value or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not _HOST.match(host) or parsed.username or parsed.port:
        raise JiraError("Enter your Jira Cloud address, like https://your-team.atlassian.net")
    return f"https://{host}"


def _explain(response: httpx.Response, doing: str) -> JiraError:
    if response.status_code in (401, 403):
        return JiraError(f"Jira refused the sign-in while {doing}. Check the email and API token, and that the account can use this project.")
    if response.status_code == 404:
        return JiraError(f"Jira could not find what was needed while {doing}. Check the project key.")
    detail = ""
    try:
        body = response.json()
        detail = "; ".join(list(body.get("errorMessages") or []) + [f"{k}: {v}" for k, v in (body.get("errors") or {}).items()])
    except ValueError:
        pass
    return JiraError(f"Jira answered with an error while {doing}{': ' + detail[:300] if detail else f' (status {response.status_code})'}")


async def check_connection(base_url: str, email: str, token: str, project_key: str, issue_type: str) -> dict:
    """Confirm the credentials work and the project accepts this issue type. Returns the project's name."""
    try:
        async with httpx.AsyncClient(timeout=20, auth=(email, token)) as client:
            me = await client.get(f"{base_url}/rest/api/3/myself")
            if me.status_code != 200:
                raise _explain(me, "signing in")
            project = await client.get(f"{base_url}/rest/api/3/project/{project_key}")
            if project.status_code != 200:
                raise _explain(project, f"opening project {project_key}")
    except httpx.HTTPError:
        raise JiraError("Jira could not be reached. Check the address and try again.")
    data = project.json()
    types = [t.get("name", "") for t in data.get("issueTypes") or [] if not t.get("subtask")]
    if types and issue_type.lower() not in [t.lower() for t in types]:
        raise JiraError(f"Project {project_key} has no issue type called {issue_type}. It has: {', '.join(types)}.")
    return {"project_name": data.get("name", project_key), "issue_types": types}


def _paragraph(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _heading(text: str) -> dict:
    return {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": text}]}


def issue_fields(finding: dict, scan_label: str, scan_url: str, project_key: str, issue_type: str) -> dict:
    """The Jira issue for one finding. The description uses Atlassian's document format."""
    severity = str(finding.get("severity", "")).lower()
    content: list[dict] = [_paragraph(f"Found by Wiseflow in a scan of {scan_label}. Severity: {severity or 'not rated'}.")]
    where = " ".join(p for p in (finding.get("method"), finding.get("affected_url")) if p)
    for title, text in (
        ("Where", where),
        ("What was found", finding.get("description") or finding.get("detail")),
        ("How to fix it", finding.get("remediation")),
        ("Reference", ", ".join(p for p in (finding.get("owasp_category"), finding.get("cwe_id")) if p)),
    ):
        if text:
            content += [_heading(title), _paragraph(str(text)[:4000])]
    proof = "\n\n".join(str(p) for p in (finding.get("proof_request"), finding.get("proof_response")) if p)
    if proof:
        content += [_heading("Evidence"), {"type": "codeBlock", "content": [{"type": "text", "text": proof[:6000]}]}]
    content.append({"type": "paragraph", "content": [{"type": "text", "text": "Open the scan in Wiseflow", "marks": [{"type": "link", "attrs": {"href": scan_url}}]}]})
    return {
        "project": {"key": project_key},
        "issuetype": {"name": issue_type},
        "summary": f"[{severity.capitalize() or 'Finding'}] {finding.get('title', 'Security finding')}"[:250],
        "description": {"type": "doc", "version": 1, "content": content},
        "labels": ["wiseflow"] + ([_SEVERITY_LABEL[severity]] if severity in _SEVERITY_LABEL else []),
    }


async def create_issue(base_url: str, email: str, token: str, fields: dict) -> tuple[str, str]:
    """Create the issue. Returns (issue key, link to it)."""
    try:
        async with httpx.AsyncClient(timeout=30, auth=(email, token)) as client:
            r = await client.post(f"{base_url}/rest/api/3/issue", json={"fields": fields})
    except httpx.HTTPError:
        raise JiraError("Jira could not be reached. Try again.")
    if r.status_code not in (200, 201):
        raise _explain(r, "creating the issue")
    key = r.json().get("key")
    if not key:
        raise JiraError("Jira did not return an issue key")
    return key, f"{base_url}/browse/{key}"
