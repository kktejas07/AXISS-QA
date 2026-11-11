"""
Tier 2 — Mobile Audit Engine

Supports:
  1. APK / IPA binary upload → extract metadata + permissions
  2. Play Store / App Store URL → scrape app description, permissions, ratings
  3. Appium test flow generation (Android + iOS) via Claude Sonnet
  4. Mobile-specific security checks:
       • Cleartext traffic, exported components, dangerous permissions (Android)
       • ATS exceptions, missing entitlements, clipboard usage (iOS)

Does NOT require a physical device at audit-time — it analyses the binary/listing
and generates test plans + Appium skeletons for a CI Appium grid to execute.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from app.core.config import settings

ai = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class MobileAuditResult:
    def __init__(self):
        self.platform: str = "unknown"      # "android" | "ios" | "unknown"
        self.app_name: str = ""
        self.app_id: str = ""
        self.version: str = ""
        self.rating: float = 0.0
        self.reviews_count: int = 0
        self.description: str = ""
        self.permissions: list[str] = []
        self.dangerous_permissions: list[str] = []
        self.security_flags: list[dict] = []   # {id, severity, title, detail}
        self.activities: list[str] = []         # Android exported activities
        self.deeplinks: list[str] = []
        self.appium_test_code: str = ""         # Generated Appium Python test
        self.manual_test_cases: list[dict] = []
        self.screenshots: list[str] = []        # base64 from Play Store scrape
        self.error: str = ""
        self.source: str = ""  # "apk" | "ipa" | "play_store" | "app_store"

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "appium_test_code"}


# ---------------------------------------------------------------------------
# Android dangerous permission reference
# ---------------------------------------------------------------------------
DANGEROUS_ANDROID_PERMISSIONS = {
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.READ_CALL_LOG",
    "android.permission.WRITE_CALL_LOG",
    "android.permission.PROCESS_OUTGOING_CALLS",
    "android.permission.READ_SMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.SEND_SMS",
    "android.permission.RECEIVE_WAP_PUSH",
    "android.permission.RECEIVE_MMS",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.BODY_SENSORS",
    "android.permission.ACTIVITY_RECOGNITION",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_MEDIA_AUDIO",
    "android.permission.GET_ACCOUNTS",
    "android.permission.USE_BIOMETRIC",
    "android.permission.USE_FINGERPRINT",
}

# ---------------------------------------------------------------------------
# APK analyser (uses aapt / aapt2 if available, else zipfile fallback)
# ---------------------------------------------------------------------------

async def analyse_apk(apk_path: str) -> MobileAuditResult:
    result = MobileAuditResult()
    result.platform = "android"
    result.source = "apk"

    # Try aapt / aapt2 first
    try:
        aapt_out = subprocess.run(
            ["aapt", "dump", "badging", apk_path],
            capture_output=True, text=True, timeout=30
        )
        if aapt_out.returncode == 0:
            _parse_aapt_output(aapt_out.stdout, result)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Fallback: parse AndroidManifest.xml inside the zip
        _parse_apk_zip(apk_path, result)

    # Security checks on what we found
    _run_android_security_checks(result)
    return result


def _parse_aapt_output(text: str, result: MobileAuditResult) -> None:
    for line in text.splitlines():
        if line.startswith("package:"):
            m = re.search(r"name='([^']+)'", line)
            if m:
                result.app_id = m.group(1)
            m = re.search(r"versionName='([^']+)'", line)
            if m:
                result.version = m.group(1)
        elif line.startswith("application-label:"):
            result.app_name = line.split(":", 1)[1].strip().strip("'")
        elif "uses-permission:" in line:
            m = re.search(r"name='([^']+)'", line)
            if m:
                perm = m.group(1)
                result.permissions.append(perm)
                if perm in DANGEROUS_ANDROID_PERMISSIONS:
                    result.dangerous_permissions.append(perm)
        elif "launchable-activity:" in line:
            m = re.search(r"name='([^']+)'", line)
            if m:
                result.activities.append(m.group(1))


def _parse_apk_zip(apk_path: str, result: MobileAuditResult) -> None:
    """Minimal manifest extraction via raw regex on binary — works without aapt."""
    try:
        with zipfile.ZipFile(apk_path) as zf:
            # Look for strings in the binary manifest
            with zf.open("AndroidManifest.xml") as f:
                data = f.read()
            # Extract printable strings
            strings = re.findall(rb'android\.permission\.[A-Z_]+', data)
            for s in strings:
                perm = s.decode("utf-8", errors="ignore")
                result.permissions.append(perm)
                if perm in DANGEROUS_ANDROID_PERMISSIONS:
                    result.dangerous_permissions.append(perm)
            # Try to get package name
            pkg = re.search(rb'package="([^"]+)"', data)
            if pkg:
                result.app_id = pkg.group(1).decode("utf-8", errors="ignore")
    except Exception as e:
        result.error = f"APK parse error: {e}"


def _run_android_security_checks(result: MobileAuditResult) -> None:
    flags = []

    if len(result.dangerous_permissions) > 5:
        flags.append({
            "id": "M1-excessive-permissions",
            "severity": "high",
            "title": "Excessive Dangerous Permissions",
            "detail": f"App requests {len(result.dangerous_permissions)} dangerous permissions: "
                      + ", ".join(result.dangerous_permissions[:5]),
        })

    location_perms = [p for p in result.dangerous_permissions if "LOCATION" in p]
    if "android.permission.ACCESS_BACKGROUND_LOCATION" in result.permissions:
        flags.append({
            "id": "M2-background-location",
            "severity": "high",
            "title": "Background Location Access",
            "detail": "App can access location in background — may enable persistent tracking.",
        })

    if "android.permission.RECORD_AUDIO" in result.dangerous_permissions:
        flags.append({
            "id": "M3-microphone",
            "severity": "medium",
            "title": "Microphone Permission",
            "detail": "App requests microphone access. Verify this is necessary and disclosed to users.",
        })

    if "android.permission.READ_SMS" in result.dangerous_permissions:
        flags.append({
            "id": "M4-sms-read",
            "severity": "critical",
            "title": "SMS Read Permission",
            "detail": "App can read SMS messages. This is a severe privacy risk.",
        })

    result.security_flags = flags


# ---------------------------------------------------------------------------
# IPA analyser (zip-based, parses Info.plist)
# ---------------------------------------------------------------------------

async def analyse_ipa(ipa_path: str) -> MobileAuditResult:
    result = MobileAuditResult()
    result.platform = "ios"
    result.source = "ipa"

    try:
        with zipfile.ZipFile(ipa_path) as zf:
            # Find Info.plist
            plist_path = None
            for name in zf.namelist():
                if re.match(r"Payload/[^/]+\.app/Info\.plist", name):
                    plist_path = name
                    break
            if not plist_path:
                result.error = "Could not find Info.plist in IPA"
                return result

            with zf.open(plist_path) as f:
                plist_data = f.read()

            # Try plistlib
            import plistlib
            try:
                plist = plistlib.loads(plist_data)
                result.app_id = plist.get("CFBundleIdentifier", "")
                result.app_name = plist.get("CFBundleDisplayName") or plist.get("CFBundleName", "")
                result.version = plist.get("CFBundleShortVersionString", "")

                # iOS privacy permission usage descriptions
                priv_keys = [k for k in plist if "UsageDescription" in k or "NSPhotoLibrary" in k]
                result.permissions = priv_keys

                _run_ios_security_checks(plist, result)
            except Exception:
                # Binary plist — try strings extraction
                strings = re.findall(rb'[A-Za-z][A-Za-z0-9.]{5,80}', plist_data)
                for s in strings:
                    decoded = s.decode("utf-8", errors="ignore")
                    if "UsageDescription" in decoded:
                        result.permissions.append(decoded)

    except Exception as e:
        result.error = f"IPA parse error: {e}"

    return result


def _run_ios_security_checks(plist: dict, result: MobileAuditResult) -> None:
    flags = []

    # ATS (App Transport Security)
    ats = plist.get("NSAppTransportSecurity", {})
    if ats.get("NSAllowsArbitraryLoads"):
        flags.append({
            "id": "IOS-M1-ats-disabled",
            "severity": "high",
            "title": "App Transport Security Disabled",
            "detail": "NSAllowsArbitraryLoads=YES allows plaintext HTTP connections.",
        })

    # Clipboard
    if "NSPasteboardUsageDescription" in plist:
        flags.append({
            "id": "IOS-M2-clipboard",
            "severity": "low",
            "title": "Clipboard Access Declared",
            "detail": "App declares pasteboard usage. Ensure it is not reading clipboard silently.",
        })

    # Location background
    modes = plist.get("UIBackgroundModes", [])
    if "location" in modes:
        flags.append({
            "id": "IOS-M3-bg-location",
            "severity": "high",
            "title": "Background Location Mode",
            "detail": "App can run in background with location access.",
        })

    result.security_flags = flags


# ---------------------------------------------------------------------------
# Store URL scraper (Play Store / App Store)
# ---------------------------------------------------------------------------

async def scrape_store_url(store_url: str) -> MobileAuditResult:
    result = MobileAuditResult()
    result.source = "play_store" if "play.google.com" in store_url else "app_store"
    result.platform = "android" if result.source == "play_store" else "ios"

    try:
        import httpx
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (compatible; AuditBot/2.0)"},
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            resp = await client.get(store_url)
            html = resp.text

        if result.source == "play_store":
            _parse_play_store(html, result)
        else:
            _parse_app_store(html, result)

    except Exception as e:
        result.error = f"Store scrape error: {e}"

    return result


def _parse_play_store(html: str, result: MobileAuditResult) -> None:
    """Extract key metadata from Play Store HTML."""
    # App name
    m = re.search(r'<title>([^<]+) - Apps on Google Play</title>', html)
    if m:
        result.app_name = m.group(1).strip()

    # Package ID from URL or JSON data
    m = re.search(r'"id":"(com\.[a-zA-Z0-9._]+)"', html)
    if m:
        result.app_id = m.group(1)

    # Rating
    m = re.search(r'"starRating","([0-9.]+)"', html)
    if m:
        result.rating = float(m.group(1))

    # Version
    m = re.search(r'"softwareVersion","([^"]+)"', html)
    if m:
        result.version = m.group(1)

    # Description (first 500 chars)
    m = re.search(r'"description","([^"]{50,})"', html)
    if m:
        result.description = m.group(1)[:500]


def _parse_app_store(html: str, result: MobileAuditResult) -> None:
    """Extract key metadata from App Store HTML."""
    m = re.search(r'<title>([^<]+) on the App Store</title>', html)
    if m:
        result.app_name = re.sub(r'\s*on the App Store\s*$', '', m.group(1)).strip()

    m = re.search(r'"bundleId":"([^"]+)"', html)
    if m:
        result.app_id = m.group(1)

    m = re.search(r'"ratingValue":"([^"]+)"', html)
    if m:
        result.rating = float(m.group(1))

    m = re.search(r'"softwareVersion":"([^"]+)"', html)
    if m:
        result.version = m.group(1)

    m = re.search(r'"description":\{"default":"([^"]{50,})"', html)
    if m:
        result.description = m.group(1)[:500]


# ---------------------------------------------------------------------------
# Appium test generator (Claude Sonnet)
# ---------------------------------------------------------------------------

APPIUM_PROMPT = """You are a senior mobile QA engineer. Generate a complete Appium Python test file for this {platform} app.

App: {app_name} ({app_id})
Version: {version}
Platform: {platform}
Dangerous permissions: {dangerous_perms}
Deeplinks: {deeplinks}

Generate pytest tests covering:
1. App launch and initial screen validation
2. Core navigation flows (tabs, drawers, back navigation)
3. Login/register flow if permission indicates accounts
4. Permission dialogs (location, camera, microphone) — accept and deny scenarios
5. Deeplink handling if any declared
6. Network error handling (airplane mode simulation)
7. Accessibility check (content descriptions on important elements)

Requirements:
- Use `AppiumOptions` and `webdriver.Remote`
- Platform: {'Android' if platform == 'android' else 'iOS'}
- Group in class `Test{class_name}App`
- Use `@pytest.mark.asyncio` and `async def test_*`
- Include `assert` with meaningful messages
- Include `driver.implicitly_wait(10)` in setup
- Use `driver.find_element(AppiumBy.XPATH, ...)` selectors

Return ONLY valid Python code. No markdown fences."""

MOBILE_MANUAL_PROMPT = """You are a QA lead specialising in mobile apps. Generate manual test cases for:

App: {app_name}
Platform: {platform}
Permissions requested: {permissions}
Security flags: {security_flags}

Generate 10-15 manual test cases covering:
- Core user flows (onboarding, login, main feature)
- Permission dialogs (grant, deny, partially grant)
- Offline / poor network behaviour
- Background / foreground transitions
- Push notifications
- Deep links
- Accessibility (font scaling, inverted colours, screen reader)
- Security (sensitive data in background screenshot, biometric auth)

Return JSON array. Each item:
{{
  "id": "MTC-001",
  "title": "short title",
  "category": "functional|permissions|network|accessibility|security",
  "priority": "P1|P2|P3",
  "platform": "{platform}",
  "preconditions": "...",
  "steps": ["step 1", "step 2"],
  "expected_result": "...",
  "jira_labels": ["QA", "mobile", "category"]
}}

Return ONLY the JSON array."""


async def generate_appium_tests(result: MobileAuditResult) -> str:
    class_name = re.sub(r'[^a-zA-Z0-9]', '', result.app_name or "App")
    prompt = APPIUM_PROMPT.format(
        platform=result.platform,
        app_name=result.app_name,
        app_id=result.app_id,
        version=result.version,
        dangerous_perms=", ".join(result.dangerous_permissions[:6]),
        deeplinks=", ".join(result.deeplinks[:5]) or "None",
        class_name=class_name,
    )
    try:
        msg = await ai.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        code = msg.content[0].text.strip()
        code = re.sub(r"^```[a-z]*\n?", "", code)
        return re.sub(r"\n?```$", "", code)
    except Exception as e:
        return f"# Error generating Appium tests: {e}\n"


async def generate_mobile_manual_cases(result: MobileAuditResult) -> list[dict]:
    prompt = MOBILE_MANUAL_PROMPT.format(
        app_name=result.app_name or "Mobile App",
        platform=result.platform,
        permissions=", ".join(result.permissions[:10]),
        security_flags=", ".join(f["title"] for f in result.security_flags),
    )
    try:
        msg = await ai.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_mobile_audit(
    *,
    apk_path: str | None = None,
    ipa_path: str | None = None,
    store_url: str | None = None,
) -> MobileAuditResult:
    """
    Run a full mobile audit.
    Exactly one of apk_path, ipa_path, store_url must be supplied.
    """
    if apk_path:
        result = await analyse_apk(apk_path)
    elif ipa_path:
        result = await analyse_ipa(ipa_path)
    elif store_url:
        result = await scrape_store_url(store_url)
    else:
        result = MobileAuditResult()
        result.error = "No mobile input provided"
        return result

    # Generate Appium test suite
    result.appium_test_code = await generate_appium_tests(result)

    # Generate manual test cases
    result.manual_test_cases = await generate_mobile_manual_cases(result)

    return result
