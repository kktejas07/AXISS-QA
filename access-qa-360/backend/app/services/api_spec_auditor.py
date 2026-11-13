"""
Reviews an API from its description file (OpenAPI 3 or Swagger 2, JSON or YAML).

The file is only read: it lists every endpoint, so missing sign-in rules,
secrets in addresses and undocumented errors can be found without calling the API.
"""
from __future__ import annotations

import json
import re

import yaml

MAX_BYTES = 2 * 1024 * 1024
METHODS = ("get", "post", "put", "patch", "delete")
WRITES = ("post", "put", "patch", "delete")
_SENSITIVE = re.compile(r"pass(word|wd)?|secret|token|api[_-]?key|auth|ssn|card", re.I)
_PUBLIC = re.compile(r"/(login|signin|sign-in|token|register|signup|sign-up|health|status|ping|webhooks?|docs|openapi)\b", re.I)


class SpecError(Exception):
    pass


def parse(raw: bytes) -> dict:
    if len(raw) > MAX_BYTES:
        raise SpecError("That file is larger than 2 MB. Upload the API description on its own.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SpecError("That file is not text. Upload an OpenAPI or Swagger file in JSON or YAML.")
    try:
        spec = json.loads(text) if text.lstrip().startswith("{") else yaml.safe_load(text)
    except (ValueError, yaml.YAMLError):
        raise SpecError("That file could not be read as JSON or YAML.")
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict) or not (spec.get("openapi") or spec.get("swagger")):
        raise SpecError("That does not look like an OpenAPI or Swagger file: it has no version and list of paths.")
    if not spec["paths"]:
        raise SpecError("That API description lists no endpoints.")
    return spec


def _schemes(spec: dict) -> dict:
    return (spec.get("components") or {}).get("securitySchemes") or spec.get("securityDefinitions") or {}


def operations(spec: dict) -> list[dict]:
    """Every endpoint as {method, path, summary, secured, parameters, responses, has_body}."""
    out = []
    default_security = spec.get("security")
    for path, item in spec["paths"].items():
        if not isinstance(item, dict):
            continue
        shared = item.get("parameters") or []
        for method in METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            security = op["security"] if "security" in op else default_security
            params = [p for p in shared + (op.get("parameters") or []) if isinstance(p, dict)]
            out.append({
                "method": method.upper(), "path": str(path), "summary": str(op.get("summary") or op.get("operationId") or "")[:200],
                "secured": bool(security) and any(security), "parameters": params,
                "responses": [str(code) for code in (op.get("responses") or {})],
                "has_body": "requestBody" in op or any(p.get("in") == "body" for p in params),
            })
    return out


def _finding(check: str, severity: str, title: str, description: str, where: str, fix: str, cwe: str = "") -> dict:
    return {"check": check, "severity": severity, "title": title, "description": description, "affected_url": where, "remediation": fix, "cwe_id": cwe}


def review(spec: dict) -> list[dict]:
    ops = operations(spec)
    schemes = _schemes(spec)
    found: list[dict] = []

    if not schemes:
        found.append(_finding("auth", "high", "The API describes no way to sign in",
                              "No security scheme is defined, so every endpoint is documented as open to anyone.", "The whole API",
                              "Define a security scheme (for example bearer tokens) and require it on every endpoint that is not meant to be public.", "CWE-306"))
    for name, scheme in schemes.items():
        if not isinstance(scheme, dict):
            continue
        if scheme.get("type") == "apiKey" and scheme.get("in") == "query":
            found.append(_finding("auth", "medium", "API key is sent in the web address",
                                  f"The scheme “{name}” puts the key in the query string, where it is saved in server logs and browser history.", f"Security scheme {name}",
                                  "Send the key in a request header instead.", "CWE-598"))
        if scheme.get("type") == "basic" or (scheme.get("type") == "http" and str(scheme.get("scheme")).lower() == "basic"):
            found.append(_finding("auth", "low", "Basic sign-in sends the password with every request",
                                  f"The scheme “{name}” uses HTTP Basic, which repeats the password on each call.", f"Security scheme {name}",
                                  "Use short-lived tokens instead, and require HTTPS.", "CWE-522"))

    servers = [s.get("url", "") for s in spec.get("servers") or [] if isinstance(s, dict)]
    if "http" in (spec.get("schemes") or []):
        servers.append("http://" + str(spec.get("host") or ""))
    for url in servers:
        if url.startswith("http://") and not re.match(r"http://(localhost|127\.0\.0\.1)", url):
            found.append(_finding("transport", "medium", "The API is offered without encryption",
                                  "A server address starts with http://, so requests and sign-in details can be read on the network.", url,
                                  "Serve the API over https:// only.", "CWE-319"))

    if schemes:
        for op in ops:
            where = f"{op['method']} {op['path']}"
            if not op["secured"] and not _PUBLIC.search(op["path"]):
                write = op["method"].lower() in WRITES
                found.append(_finding("auth", "high" if write else "medium", "Endpoint needs no sign-in",
                                      f"{where} has no security requirement, so it is documented as open to anyone" + (" even though it changes data." if write else "."), where,
                                      "Add the security requirement, or mark the endpoint as public on purpose and review what it returns.", "CWE-306"))
    for op in ops:
        where = f"{op['method']} {op['path']}"
        for p in op["parameters"]:
            if p.get("in") == "query" and _SENSITIVE.search(str(p.get("name") or "")):
                found.append(_finding("data", "medium", "Sensitive value sent in the web address",
                                      f"The parameter “{p.get('name')}” is sent in the query string, where it is saved in logs and browser history.", where,
                                      "Send it in the request body or a header instead.", "CWE-598"))
        codes = op["responses"]
        if not any(c.startswith("4") or c == "default" for c in codes):
            found.append(_finding("errors", "low", "No error responses are documented",
                                  f"{where} lists no 4xx response, so callers cannot tell what a refused or invalid request looks like.", where,
                                  "Document at least the 400, 401 or 403, and 404 responses.", ""))
        if op["secured"] and codes and not any(c in ("401", "403", "default") for c in codes):
            found.append(_finding("errors", "low", "No “not allowed” response is documented",
                                  f"{where} needs sign-in but documents no 401 or 403 response.", where, "Document the 401 and 403 responses.", ""))
        if re.search(r"/(login|signin|sign-in|token|password)", op["path"], re.I) and op["method"] == "POST" and "429" not in codes:
            found.append(_finding("auth", "low", "No limit on sign-in attempts is documented",
                                  f"{where} documents no 429 response, which suggests repeated guesses are not slowed down.", where,
                                  "Limit attempts per account and address, and document the 429 response.", "CWE-307"))

    order = ["critical", "high", "medium", "low"]
    return sorted(found, key=lambda f: order.index(f["severity"]))[:300]


def test_cases(spec: dict) -> list[dict]:
    """Manual test cases for each endpoint: it works, it refuses strangers, it rejects bad input."""
    cases: list[dict] = []

    def add(op: dict, title: str, steps: list[str], expected: str, priority: str, category: str) -> None:
        cases.append({"id": f"API-{len(cases) + 1:03d}", "title": title, "category": category, "priority": priority,
                      "preconditions": "A running copy of the API and, where needed, a valid sign-in token.",
                      "steps": steps, "expected_result": expected, "page_url": f"{op['method']} {op['path']}"})

    for op in operations(spec)[:150]:
        where = f"{op['method']} {op['path']}"
        ok = next((c for c in op["responses"] if c.startswith("2")), "200")
        add(op, f"{where} works with valid input", [f"Send {where} with valid values" + (" and a valid token" if op["secured"] else ""), "Read the response"],
            f"The response is {ok} and matches the documented shape.", "High", "Functional")
        if op["secured"]:
            add(op, f"{where} refuses a caller who is not signed in", [f"Send {where} with no token", f"Send {where} with an expired or made-up token"],
                "Both calls are refused with 401, and no data is returned.", "High", "Security")
        if "{" in op["path"]:
            add(op, f"{where} handles an item that does not exist", [f"Send {where} with an id that does not exist"], "The response is 404 with a clear message.", "Medium", "Negative")
            if op["secured"]:
                add(op, f"{where} refuses another user's item", ["Sign in as user A and note the id of one of their items", f"Sign in as user B and send {where} with that id"],
                    "The call is refused with 403 or 404. User B never sees or changes user A's item.", "High", "Security")
        if op["has_body"] or any(p.get("required") for p in op["parameters"]):
            add(op, f"{where} rejects missing or invalid input", [f"Send {where} leaving out a required value", f"Send {where} with a value of the wrong type or an over-long string"],
                "Each call is refused with 400 or 422 and says which value is wrong. Nothing is saved.", "Medium", "Negative")
    return cases


def overview(spec: dict) -> dict:
    info = spec.get("info") or {}
    ops = operations(spec)
    return {
        "title": str(info.get("title") or "Untitled API")[:200], "version": str(info.get("version") or "")[:40],
        "format": f"OpenAPI {spec['openapi']}" if spec.get("openapi") else f"Swagger {spec.get('swagger')}",
        "operations": len(ops), "secured": sum(1 for o in ops if o["secured"]),
        "endpoints": [{k: o[k] for k in ("method", "path", "summary", "secured")} for o in ops[:300]],
    }
