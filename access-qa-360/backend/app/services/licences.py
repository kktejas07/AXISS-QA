"""
Which licence each package in a code scan is under, and which ones need a second look.

Licences are looked up from the public package registries (PyPI and npm), which
is the only way to know them without downloading every package. Other kinds of
package are counted and reported as not looked up, never guessed.

This sorts licences into broad groups to show where to look. It is not legal advice.
"""
from __future__ import annotations

import asyncio
import re
from urllib.parse import quote

import httpx

MAX_PACKAGES = 300
LOOKED_UP = ("PyPI", "npm")

# group -> (what it means for someone shipping a product, words that put a licence in it). Checked in this order.
GROUPS: list[tuple[str, str, tuple[str, ...]]] = [
    ("strong", "Asks you to release your own source code under the same licence if you distribute (AGPL, SSPL: even if you only run it as a service).",
     ("agpl", "affero", "sspl", "server side public", "gpl", "gnu general public", "eupl", "osl", "cc-by-sa", "sleepycat")),
    ("weak", "Changes to the package itself must be shared; your own code can stay closed.",
     ("lgpl", "lesser general public", "mpl", "mozilla public", "epl", "eclipse public", "cddl", "cpl", "common public")),
    ("permissive", "Free to use in a closed product; keep the copyright notice.",
     ("mit", "apache", "bsd", "isc", "unlicense", "0bsd", "zlib", "python software foundation", "psf", "cc0", "wtfpl", "public domain", "boost", "bsl-1.0", "artistic", "postgresql", "hpnd", "blueoak", "zpl", "upl")),
]
ABOUT = {name: about for name, about, _ in GROUPS} | {
    "unknown": "No licence could be found, or it is not a standard one. Without a licence you have no right to use the code, so check these by hand.",
}


def classify(licence: str | None) -> str:
    text = (licence or "").lower()
    if not text.strip() or text.strip() in ("unknown", "unlicensed", "see license", "see licence", "proprietary", "none", "other/proprietary license"):
        return "unknown"
    # "X OR Y" lets you choose the easier one; "X AND Y" binds you to the stricter one.
    # A word only counts at the start of a name, so the "gpl" in "LGPL" is not read as GPL.
    choices = [part for part in re.split(r"\s+or\s+|/", text) if part.strip()] or [text]
    order = {"permissive": 0, "weak": 1, "strong": 2, "unknown": 3}
    found = []
    for part in choices:
        groups = [name for name, _, words in GROUPS if any(re.search(rf"(?<![a-z]){re.escape(word)}", part) for word in words)]
        found.append(max(groups, key=order.get) if groups else "unknown")
    return min(found, key=order.get)


def _pypi(data: dict) -> str | None:
    info = data.get("info") or {}
    if info.get("license_expression"):
        return info["license_expression"]
    named = [c.split("::")[-1].strip() for c in info.get("classifiers") or [] if c.startswith("License ::")]
    if named:
        return " OR ".join(named) if len(named) > 1 else named[0]
    text = (info.get("license") or "").strip()
    # Some projects paste the whole licence text here; the first line names it.
    return text.splitlines()[0][:80] if text else None


def _npm(data: dict) -> str | None:
    licence = data.get("license") or data.get("licenses")
    if isinstance(licence, list):
        licence = " OR ".join(str((item or {}).get("type", "")) if isinstance(item, dict) else str(item) for item in licence)
    if isinstance(licence, dict):
        licence = licence.get("type")
    return str(licence)[:80] if licence else None


async def _one(client: httpx.AsyncClient, gate: asyncio.Semaphore, package: dict) -> str | None:
    name, version = package["name"], package["version"]
    if package["ecosystem"] == "PyPI":
        url, read = f"https://pypi.org/pypi/{quote(name, safe='')}/{quote(version, safe='')}/json", _pypi
    else:
        url, read = f"https://registry.npmjs.org/{quote(name, safe='@')}/{quote(version, safe='')}", _npm
    async with gate:
        try:
            r = await client.get(url)
            return read(r.json()) if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            return None


async def report(packages: list[dict]) -> dict:
    """Look up and sort the licences of a scan's packages."""
    unique = list({(p["ecosystem"], p["name"].lower(), p["version"]): p for p in packages}.values())
    can = [p for p in unique if p["ecosystem"] in LOOKED_UP]
    chosen = can[:MAX_PACKAGES]
    gate = asyncio.Semaphore(12)
    async with httpx.AsyncClient(timeout=8, follow_redirects=False, headers={"User-Agent": "Wiseflow licence check"}) as client:
        found = await asyncio.gather(*(_one(client, gate, p) for p in chosen))
    rows = [{"ecosystem": p["ecosystem"], "name": p["name"], "version": p["version"], "manifest": p["manifest"],
             "licence": licence or "Not found", "group": classify(licence)} for p, licence in zip(chosen, found)]
    order = {"strong": 0, "unknown": 1, "weak": 2, "permissive": 3}
    rows.sort(key=lambda r: (order[r["group"]], r["name"].lower()))
    return {
        "counts": {group: sum(1 for r in rows if r["group"] == group) for group in order},
        "about": ABOUT,
        "packages": rows,
        "checked": len(rows),
        "not_looked_up": len(unique) - len(can),          # kinds of package other than PyPI and npm
        "over_limit": len(can) - len(chosen),
    }
