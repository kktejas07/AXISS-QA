"""
Source code scanning: reads an uploaded .zip or a cloned repository without running it.

What it produces
  inventory      files read, languages, HTTP routes found
  findings       leaked secrets, risky code, vulnerable dependencies (same shape as web findings)
  qa gaps        source files and routes that no test refers to

Everything here is static. Nothing from the scanned project is executed, installed or imported.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app.core.config import settings

# ---------------------------------------------------------------------------
# What gets read
# ---------------------------------------------------------------------------

LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin", ".go": "Go", ".rb": "Ruby",
    ".php": "PHP", ".cs": "C#", ".swift": "Swift", ".dart": "Dart", ".rs": "Rust", ".vue": "Vue", ".svelte": "Svelte",
}
CONFIG_EXTENSIONS = {
    ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".properties", ".xml", ".tf", ".sh",
    ".env", ".pem", ".key", ".txt", ".lock", ".mod", ".gradle", ".sql", ".html",
}
CONFIG_NAMES = {"dockerfile", "gemfile", "pipfile", "makefile", "procfile"}
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "target", ".venv", "venv", "env", "__pycache__",
    ".next", ".nuxt", ".idea", ".vscode", "coverage", ".gradle", "pods", ".dart_tool", "bower_components",
    ".tox", ".mypy_cache", ".pytest_cache", "site-packages",
}
LOCK_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "pipfile.lock", "composer.lock", "gemfile.lock", "go.sum", "cargo.lock"}
MAX_FILE_BYTES = 1_000_000
DEPTH_FILES = {"quick": 800, "standard": 4000, "deep": 12000}
DEPTH_PACKAGES = {"quick": 150, "standard": 600, "deep": 1500}
MAX_FINDINGS_PER_RULE = 15
REPO_HOSTS = {"github.com", "gitlab.com", "bitbucket.org"}


class SourceError(Exception):
    """A problem with the upload or repository that the user can act on."""


def _wanted(name: str) -> bool:
    lower = name.lower()
    ext = os.path.splitext(lower)[1]
    return ext in LANGUAGES or ext in CONFIG_EXTENSIONS or lower in CONFIG_NAMES or lower.startswith(".env") or lower.startswith("dockerfile")


def _skipped_dir(parts: list[str]) -> bool:
    return any(p.lower() in SKIP_DIRS for p in parts)


# ---------------------------------------------------------------------------
# Getting the source onto disk
# ---------------------------------------------------------------------------

def parse_repo_url(url: str) -> tuple[str, str]:
    """Return (clone url, "owner/name") for a public GitHub, GitLab or Bitbucket repository."""
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if parsed.scheme != "https" or host not in REPO_HOSTS:
        raise SourceError("Enter an https:// link to a repository on GitHub, GitLab or Bitbucket")
    if parsed.params or " " in url.strip():
        raise SourceError("The link should look like https://github.com/owner/repository")
    if parsed.username or parsed.password:
        raise SourceError("Remove the username or token from the link. Only public repositories can be scanned for now.")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or not all(re.fullmatch(r"[A-Za-z0-9._-]+", p) for p in parts):
        raise SourceError("The link should look like https://github.com/owner/repository")
    # GitLab allows nested groups; GitHub and Bitbucket links can carry /tree/main and the like.
    if host != "gitlab.com":
        parts = parts[:2]
    parts[-1] = parts[-1].removesuffix(".git")
    name = "/".join(parts)
    return f"https://{host}/{name}.git", name


_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$")


def clone_repo(url: str, dest: str, timeout: int = 180, ref: str | None = None, token: str | None = None) -> None:
    """
    Shallow-clone one branch (the default one unless `ref` names another). No prompts, no submodules.
    A token, when given, is sent as a request header and never written to disk.
    """
    clone_url, name = parse_repo_url(url)
    if ref and (not _REF.match(ref) or ".." in ref):
        raise SourceError("That branch name cannot be used")
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true", "GIT_LFS_SKIP_SMUDGE": "1"}
    command = ["git", "-c", "core.hooksPath=/dev/null"]
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        command += ["-c", f"http.extraHeader=Authorization: Basic {basic}"]
    command += ["clone", "--depth", "1", "--single-branch", "--no-tags"] + (["--branch", ref] if ref else []) + [clone_url, dest]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise SourceError(f"Cloning {name} took longer than {timeout} seconds. Try uploading a .zip of the code instead.")
    except FileNotFoundError:
        raise SourceError("Repository scanning is not set up on this server (git is missing)")
    if done.returncode != 0:
        raise SourceError(f"Could not clone {name}. Check the link, and that the repository is public.")
    shutil.rmtree(os.path.join(dest, ".git"), ignore_errors=True)


def extract_zip(zip_path: str, dest: str) -> int:
    """
    Unpack only the files the scan reads. Entries that point outside the folder,
    links and oversized files are left out. Returns the number of files written.
    """
    limit = settings.CODE_SCAN_MAX_MB * 1024 * 1024
    root = os.path.realpath(dest)
    written = total = 0
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise SourceError("That file is not a valid .zip archive")
    with archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > 200_000:
            raise SourceError("The archive holds too many files to scan")
        # Archives made by GitHub and most tools wrap everything in one folder; drop it from paths.
        tops = {i.filename.replace("\\", "/").split("/", 1)[0] for i in infos}
        strip = len(tops) == 1 and all("/" in i.filename.replace("\\", "/") for i in infos)
        for info in infos:
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p]
            if strip:
                parts = parts[1:]
            if not parts or any(p == ".." for p in parts) or name.startswith("/"):
                continue
            if stat.S_ISLNK(info.external_attr >> 16):
                continue
            if _skipped_dir(parts[:-1]) or not _wanted(parts[-1]) or info.file_size > MAX_FILE_BYTES:
                continue
            target = os.path.realpath(os.path.join(root, *parts))
            if not target.startswith(root + os.sep):
                continue
            total += info.file_size
            if total > limit:
                raise SourceError(f"The code in this archive is larger than {settings.CODE_SCAN_MAX_MB} MB once unpacked")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            written += 1
    if written == 0:
        raise SourceError("No source code was found in that archive")
    return written


# ---------------------------------------------------------------------------
# Reading the tree
# ---------------------------------------------------------------------------

@dataclass
class SourceFile:
    path: str            # relative, forward slashes
    text: str
    language: str | None
    is_test: bool

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()


_TEST_FILE = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|e2e|cypress|androidtest)/|(^|/)(test_[^/]+|[^/]+_test|conftest)\.py$"
    r"|\.(test|spec)\.[jt]sx?$|Tests?\.(java|kt|cs|swift)$|_test\.(go|dart|rb)$|_spec\.rb$",
    re.I,
)


def read_tree(root: str, depth: str = "standard") -> tuple[list[SourceFile], bool]:
    """Read the text files worth scanning. The bool says whether the file limit cut the read short."""
    limit = DEPTH_FILES.get(depth, DEPTH_FILES["standard"])
    files: list[SourceFile] = []
    truncated = False
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS)
        for name in sorted(names):
            if not _wanted(name):
                continue
            full = os.path.join(folder, name)
            try:
                if os.path.islink(full) or os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
                with open(full, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue
            if b"\x00" in raw[:4096]:
                continue
            if len(files) >= limit:
                truncated = True
                break
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            ext = os.path.splitext(name.lower())[1]
            files.append(SourceFile(rel, raw.decode("utf-8", "replace"), LANGUAGES.get(ext), bool(_TEST_FILE.search(rel))))
        if truncated:
            break
    return files, truncated


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def _finding(check: str, severity: str, title: str, description: str, where: str, snippet: str = "",
             remediation: str = "", cwe: str = "", owasp: str = "") -> dict:
    return {
        "check": check, "severity": severity, "title": title, "description": description,
        "affected_url": where, "method": "", "proof_request": snippet,
        "remediation": remediation, "cwe_id": cwe, "owasp_category": owasp,
    }


# ---- secrets ---------------------------------------------------------------

_PLACEHOLDER = re.compile(
    r"example|changeme|change[-_]me|your[-_ ]|xxxx|placeholder|dummy|sample|redacted|todo|<|\$\{|\{\{|%\(|process\.env|os\.environ|getenv|\*\*\*",
    re.I,
)

SECRET_RULES: list[tuple[str, str, re.Pattern, int]] = [
    # (name, severity, pattern, group holding the secret)
    ("AWS access key", "critical", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"), 1),
    ("Private key", "critical", re.compile(r"(-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----)"), 1),
    ("GitHub token", "critical", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,})\b"), 1),
    ("Stripe live key", "critical", re.compile(r"\b((?:sk|rk)_live_[A-Za-z0-9]{20,})\b"), 1),
    ("Slack token", "high", re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"), 1),
    ("Google API key", "high", re.compile(r"\b(AIza[0-9A-Za-z_\-]{35})\b"), 1),
    ("AI provider API key", "high", re.compile(r"\b(sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{32,})\b"), 1),
    ("Database password in a connection string", "high",
     re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)(?:\+\w+)?://(?P<user>[^\s:/\"'@]+):([^\s@\"']{4,})@"), 2),
]
_GENERIC_SECRET = re.compile(
    r"\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key)\b"
    r"[\"']?\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']",
    re.I,
)
_WEAK_DEFAULTS = {"password", "postgres", "root", "admin", "secret", "user", "pass", "test", "guest", "mysql", "redis"}


def _in_sentence(name: str) -> str:
    """Lower-case the first letter unless the name starts with an acronym: 'Private key' -> 'private key', 'AWS access key' stays."""
    return name if name[:2].isupper() else name[0].lower() + name[1:]


def _redact(line: str, secret: str) -> str:
    shown = secret[:4] + "…(hidden)" if len(secret) > 8 else "…(hidden)"
    return line.strip().replace(secret, shown)[:240]


def _looks_real(value: str) -> bool:
    if _PLACEHOLDER.search(value) or value.lower() in _WEAK_DEFAULTS or len(set(value)) < 5:
        return False
    return len(value) >= 20 or (any(c.isdigit() for c in value) and any(c.isalpha() for c in value))


def find_secrets(files: list[SourceFile]) -> list[dict]:
    found: list[dict] = []
    counts: dict[str, int] = {}
    fix = "Remove it from the code, revoke or rotate it now, and load it from an environment variable or a secrets manager. It also stays in the Git history until that is rewritten."
    for f in files:
        base = os.path.basename(f.path).lower()
        if base in LOCK_NAMES or base.endswith((".min.js", ".map", ".example", ".sample", ".template", ".dist")):
            continue
        for number, line in enumerate(f.lines, 1):
            if len(line) > 2000:
                continue
            hits: list[tuple[str, str, str]] = []
            for name, severity, pattern, group in SECRET_RULES:
                m = pattern.search(line)
                if not m or _PLACEHOLDER.search(m.group(group)) or m.group(group).lower() in _WEAK_DEFAULTS:
                    continue
                # user:user style logins are local development defaults, not leaked credentials
                if "user" in m.groupdict() and m.group(group).lower().startswith(m.group("user").lower()):
                    continue
                hits.append((name, severity, m.group(group)))
            if not hits and not f.is_test:
                m = _GENERIC_SECRET.search(line)
                if m and _looks_real(m.group(2)):
                    kind = m.group(1).lower().replace("_", " ").replace("-", " ").replace("api", "API").replace("pwd", "password").replace("passwd", "password")
                    hits.append((f"Hard-coded {kind}", "medium", m.group(2)))
            for name, severity, secret in hits[:1]:
                counts[name] = counts.get(name, 0) + 1
                if counts[name] > MAX_FINDINGS_PER_RULE:
                    continue
                found.append(_finding(
                    "secrets", severity, f"{name} in the code",
                    f"A value that looks like a real {_in_sentence(name.removeprefix('Hard-coded '))} is written into {f.path}. Anyone who can read the code can use it.",
                    f"{f.path}:{number}", _redact(line, secret), fix,
                    "CWE-798", "A07:2021 Identification and Authentication Failures",
                ))
    return found


# ---- risky code ------------------------------------------------------------

@dataclass
class Rule:
    id: str
    title: str
    severity: str
    pattern: re.Pattern
    exts: tuple[str, ...]
    why: str
    fix: str
    cwe: str
    owasp: str


_PY = (".py",)
_JS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte")
_JVM = (".java", ".kt")
_INJ = "A03:2021 Injection"
_MISCONF = "A05:2021 Security Misconfiguration"
_CRYPTO = "A02:2021 Cryptographic Failures"

RULES: list[Rule] = [
    Rule("py-eval", "Text is run as code", "high", re.compile(r"(?<![\w.])(eval|exec)\s*\("), _PY,
         "eval or exec runs whatever text it is given. If any part of that text comes from a user, they can run their own code on the server.",
         "Replace it with explicit parsing, such as json.loads or ast.literal_eval, or a lookup table of allowed operations.", "CWE-95", _INJ),
    Rule("py-shell", "Shell command built in code", "high", re.compile(r"subprocess\.\w+\([^)]*shell\s*=\s*True|os\.(system|popen)\s*\("), _PY,
         "The command goes through a shell, so any user input inside it can add extra commands.",
         "Call subprocess.run with a list of arguments and without shell=True.", "CWE-78", _INJ),
    Rule("py-sql", "SQL query built from strings", "high",
         re.compile(r"\.execute(?:many)?\(\s*(?:f[\"']|[\"'][^\"']*[\"']\s*(?:%|\+)|[\"'][^\"']*[\"']\.format\()"), _PY,
         "The query is assembled with string formatting, so input can change the query itself (SQL injection).",
         "Pass values as query parameters instead of formatting them into the SQL text.", "CWE-89", _INJ),
    Rule("py-deserialize", "Unsafe loading of data", "medium",
         re.compile(r"pickle\.loads?\(|yaml\.load\((?![^)]*Loader\s*=\s*(?:yaml\.)?(?:Safe|CSafe)Loader)"), _PY,
         "pickle and yaml.load can run code hidden in the data they read.",
         "Use json, or yaml.safe_load, for data that did not come from your own code.", "CWE-502", "A08:2021 Software and Data Integrity Failures"),
    Rule("py-tls", "TLS certificate checks switched off", "medium", re.compile(r"verify\s*=\s*False"), _PY,
         "With verification off, the connection can be intercepted without any error.",
         "Remove verify=False. If the server uses a private certificate authority, pass its certificate instead.", "CWE-295", _CRYPTO),
    Rule("py-hash", "Weak hash function", "low", re.compile(r"hashlib\.(md5|sha1)\s*\("), _PY,
         "MD5 and SHA-1 are broken for security use. This matters if the value protects passwords, tokens or signatures.",
         "Use SHA-256 for integrity, and bcrypt, scrypt or Argon2 for passwords.", "CWE-327", _CRYPTO),
    Rule("py-debug", "Debug mode switched on", "medium", re.compile(r"^\s*DEBUG\s*=\s*True\b|\.run\([^)]*debug\s*=\s*True"), _PY,
         "Debug mode shows stack traces and settings to visitors, and some frameworks allow code to be run from the error page.",
         "Read the flag from the environment and keep it off in production.", "CWE-489", _MISCONF),
    Rule("py-cors", "Any website may call this API", "medium", re.compile(r"allow_origins\s*=\s*\[\s*[\"']\*[\"']|CORS_ORIGIN_ALLOW_ALL\s*=\s*True"), _PY,
         "A wildcard origin lets any website read responses from this API in a visitor's browser.",
         "List the exact origins that need access.", "CWE-942", _MISCONF),
    Rule("py-jwt", "Token signature is not checked", "high", re.compile(r"verify_signature[\"']?\s*:\s*False|jwt\.decode\([^)]*verify\s*=\s*False"), _PY,
         "Tokens are accepted without checking who signed them, so anyone can forge a session.",
         "Always verify the signature with the server key and a fixed list of algorithms.", "CWE-347", "A07:2021 Identification and Authentication Failures"),

    Rule("js-eval", "Text is run as code", "high", re.compile(r"(?<![\w.])eval\s*\(|new\s+Function\s*\("), _JS,
         "eval and new Function run whatever text they are given, including text an attacker controls.",
         "Parse data with JSON.parse and call named functions instead.", "CWE-95", _INJ),
    Rule("js-html", "HTML is written without escaping", "medium", re.compile(r"dangerouslySetInnerHTML|\.innerHTML\s*=|document\.write\(|v-html="), _JS,
         "If the HTML includes anything a user typed, they can inject scripts that run for other visitors (XSS).",
         "Render text as text. If HTML is really needed, pass it through a sanitiser such as DOMPurify first.", "CWE-79", _INJ),
    Rule("js-shell", "Shell command built from variables", "high", re.compile(r"\bexec(?:Sync)?\s*\(\s*(?:`[^`]*\$\{|[^,)]*\+)"), _JS,
         "A command string is assembled from variables and run through a shell, so input can add extra commands.",
         "Use execFile or spawn with an argument list.", "CWE-78", _INJ),
    Rule("js-sql", "SQL query built from strings", "high", re.compile(r"\.(?:query|execute|raw)\(\s*(?:`[^`]*\$\{|[\"'][^\"']*[\"']\s*\+)"), _JS,
         "The query is assembled from variables, so input can change the query itself (SQL injection).",
         "Use parameter placeholders and pass the values separately.", "CWE-89", _INJ),
    Rule("js-tls", "TLS certificate checks switched off", "medium", re.compile(r"rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*[\"']?0"), _JS,
         "With verification off, the connection can be intercepted without any error.",
         "Remove the setting and trust the right certificate authority instead.", "CWE-295", _CRYPTO),
    Rule("js-cors", "Any website may call this API", "medium", re.compile(r"origin\s*:\s*[\"']\*[\"']|Access-Control-Allow-Origin[\"']\s*,\s*[\"']\*"), _JS,
         "A wildcard origin lets any website read responses from this API in a visitor's browser.",
         "List the exact origins that need access.", "CWE-942", _MISCONF),
    Rule("js-token-storage", "Sign-in token kept in browser storage", "low",
         re.compile(r"(?:local|session)Storage\.setItem\(\s*[\"'][^\"']*(?:token|jwt|secret|password)", re.I), _JS,
         "Anything in localStorage can be read by any script on the page, so one XSS bug exposes the session.",
         "Prefer an HttpOnly, Secure, SameSite cookie set by the server.", "CWE-922", "A07:2021 Identification and Authentication Failures"),

    Rule("jvm-exec", "Operating system command run from code", "high", re.compile(r"Runtime\.getRuntime\(\)\.exec\("), _JVM,
         "If any part of the command comes from input, it can run other commands.",
         "Use ProcessBuilder with a fixed program and separate arguments, and validate input.", "CWE-78", _INJ),
    Rule("jvm-sql", "SQL query built from strings", "high", re.compile(r"(?:executeQuery|executeUpdate|prepareStatement|rawQuery|execSQL)\(\s*\"[^\"]*\"\s*\+"), _JVM,
         "The query is assembled by joining strings, so input can change the query itself (SQL injection).",
         "Use a prepared statement with ? placeholders.", "CWE-89", _INJ),
    Rule("jvm-hash", "Weak hash function", "low", re.compile(r"MessageDigest\.getInstance\(\s*\"(?:MD5|SHA-?1)\""), _JVM,
         "MD5 and SHA-1 are broken for security use.", "Use SHA-256, and a password hashing function for passwords.", "CWE-327", _CRYPTO),
    Rule("jvm-tls", "TLS certificate checks switched off", "medium", re.compile(r"ALLOW_ALL_HOSTNAME_VERIFIER|TrustAll|checkServerTrusted\([^)]*\)\s*\{\s*\}"), _JVM,
         "Every certificate is accepted, so the connection can be intercepted.", "Use the platform's default trust manager.", "CWE-295", _CRYPTO),

    Rule("php-exec", "Text or commands run from code", "high", re.compile(r"(?<![\w>])(eval|system|shell_exec|passthru|popen)\s*\("), (".php",),
         "These functions run code or shell commands. With user input inside, an attacker controls the server.",
         "Avoid them; where a command is needed, use escapeshellarg on every argument.", "CWE-78", _INJ),
    Rule("php-sql", "User input placed straight into SQL", "high", re.compile(r"(?:query|mysql_query|mysqli_query)\([^)]*\$_(?:GET|POST|REQUEST|COOKIE)"), (".php",),
         "Request data is put directly into the query (SQL injection).", "Use prepared statements with bound parameters.", "CWE-89", _INJ),
    Rule("php-unserialize", "Unsafe loading of data", "high", re.compile(r"unserialize\(\s*\$_(?:GET|POST|REQUEST|COOKIE)"), (".php",),
         "unserialize on request data can create objects that run code.", "Use json_decode for request data.", "CWE-502", "A08:2021 Software and Data Integrity Failures"),

    Rule("go-tls", "TLS certificate checks switched off", "medium", re.compile(r"InsecureSkipVerify\s*:\s*true"), (".go",),
         "With verification off, the connection can be intercepted without any error.", "Remove InsecureSkipVerify and trust the right certificate authority.", "CWE-295", _CRYPTO),
    Rule("go-sql", "SQL query built from strings", "high", re.compile(r"fmt\.Sprintf\(\s*\"[^\"]*\b(?:SELECT|INSERT|UPDATE|DELETE)\b", re.I), (".go",),
         "The query is assembled with Sprintf, so input can change the query itself (SQL injection).", "Use placeholders and pass values as arguments to Query or Exec.", "CWE-89", _INJ),
]

_COMMENT = re.compile(r"^\s*(#|//|\*|/\*|<!--)")
_TRIPLE = re.compile(r'''"""|\'\'\'''')
_DOC_START = re.compile(r'''^\s*[rRuUbBfF]{0,2}("""|\'\'\')''')


def _prose_lines(f: SourceFile) -> set[int]:
    """
    Line numbers that are documentation, not code: Python docstrings and other
    triple-quoted blocks. Examples inside them would otherwise be reported as
    real routes and real risky calls. A line that opens a triple-quoted string
    in the middle of a statement, such as execute(f\"\"\"...), still counts as code.
    """
    if not f.path.lower().endswith(".py"):
        return set()
    prose: set[int] = set()
    inside = False
    for number, line in enumerate(f.lines, 1):
        if inside or _DOC_START.match(line):
            prose.add(number)
        if len(_TRIPLE.findall(line)) % 2:
            inside = not inside
    return prose


def find_risky_code(files: list[SourceFile]) -> list[dict]:
    """One finding per rule and file, so a pattern repeated in one file does not flood the list."""
    found: list[dict] = []
    per_rule: dict[str, int] = {}
    for f in files:
        if f.is_test or not f.language:
            continue
        ext = os.path.splitext(f.path.lower())[1]
        rules = [r for r in RULES if ext in r.exts]
        if not rules:
            continue
        lines = f.lines
        prose = _prose_lines(f)
        for rule in rules:
            hits = [n for n, line in enumerate(lines, 1)
                    if len(line) < 2000 and n not in prose and not _COMMENT.match(line) and rule.pattern.search(line)]
            if not hits:
                continue
            per_rule[rule.id] = per_rule.get(rule.id, 0) + 1
            if per_rule[rule.id] > MAX_FINDINGS_PER_RULE:
                continue
            more = f" The same pattern appears on {len(hits) - 1} more line{'s' if len(hits) > 2 else ''} in this file: {', '.join(map(str, hits[1:8]))}." if len(hits) > 1 else ""
            found.append(_finding(
                "code", rule.severity, rule.title, rule.why + more, f"{f.path}:{hits[0]}",
                lines[hits[0] - 1].strip()[:240], rule.fix, rule.cwe, rule.owasp,
            ))
    return found


def find_config_problems(files: list[SourceFile]) -> list[dict]:
    found: list[dict] = []
    for f in files:
        base = os.path.basename(f.path).lower()
        if base.startswith(".env") and not f.is_test and not base.endswith((".example", ".sample", ".template", ".dist")):
            values = [l for l in f.lines if re.match(r"\s*[A-Z0-9_]+\s*=\s*\S", l) and not _PLACEHOLDER.search(l)]
            if values:
                found.append(_finding(
                    "config", "high", "Environment file is part of the code",
                    f"{f.path} holds {len(values)} setting{'s' if len(values) != 1 else ''} with values. These files usually carry passwords and keys and should not be shared with the code.",
                    f.path, "", "Remove the file from the repository, add it to .gitignore, rotate any real secrets in it, and commit a .env.example with empty values instead.",
                    "CWE-538", _MISCONF,
                ))
        if base.startswith("dockerfile") and re.search(r"^\s*FROM\s", f.text, re.M | re.I) and not re.search(r"^\s*USER\s+(?!root\b|0\b)\S", f.text, re.M | re.I):
            found.append(_finding(
                "config", "low", "Container runs as root",
                f"{f.path} never switches to a non-root user, so a break-in to the app gets root inside the container.",
                f.path, "", "Create a user in the image and add a USER line before the start command.", "CWE-250", _MISCONF,
            ))
    return found


# ---- dependencies ----------------------------------------------------------

@dataclass(frozen=True)
class Package:
    ecosystem: str
    name: str
    version: str
    manifest: str


def find_packages(files: list[SourceFile]) -> list[Package]:
    """Exact versions from lock files and pinned requirement files."""
    found: dict[tuple[str, str, str], Package] = {}

    def add(ecosystem: str, name: str, version: str, manifest: str) -> None:
        version = version.strip().lstrip("v=")
        if name and re.match(r"\d", version):
            found.setdefault((ecosystem, name.lower(), version), Package(ecosystem, name, version, manifest))

    has_npm_lock = any(os.path.basename(f.path).lower() in ("package-lock.json", "yarn.lock") for f in files)
    for f in files:
        base = os.path.basename(f.path).lower()
        try:
            if re.fullmatch(r"requirements[\w.-]*\.txt", base):
                for line in f.lines:
                    m = re.match(r"\s*([A-Za-z0-9._-]+)(?:\[[^\]]*\])?\s*==\s*([\w.!+-]+)", line)
                    if m:
                        add("PyPI", m.group(1), m.group(2), f.path)
            elif base == "poetry.lock":
                for m in re.finditer(r"\[\[package\]\]\s*\nname\s*=\s*\"([^\"]+)\"\s*\nversion\s*=\s*\"([^\"]+)\"", f.text):
                    add("PyPI", m.group(1), m.group(2), f.path)
            elif base == "pipfile.lock":
                data = json.loads(f.text)
                for section in ("default", "develop"):
                    for name, spec in (data.get(section) or {}).items():
                        add("PyPI", name, str((spec or {}).get("version", "")), f.path)
            elif base == "package-lock.json":
                data = json.loads(f.text)
                for key, spec in (data.get("packages") or {}).items():
                    if key and "node_modules/" in key:
                        add("npm", key.rsplit("node_modules/", 1)[1], str((spec or {}).get("version", "")), f.path)
                for name, spec in (data.get("dependencies") or {}).items():
                    add("npm", name, str((spec or {}).get("version", "")), f.path)
            elif base == "yarn.lock":
                for m in re.finditer(r"^\"?(@?[^@\"\s,]+)@[^\n]*:\n\s+version:?\s+\"?([^\"\n]+)\"?", f.text, re.M):
                    add("npm", m.group(1), m.group(2), f.path)
            elif base == "package.json" and not has_npm_lock:
                data = json.loads(f.text)
                for section in ("dependencies", "devDependencies"):
                    for name, spec in (data.get(section) or {}).items():
                        m = re.fullmatch(r"[\^~]?(\d+\.\d+\.\d+[\w.-]*)", str(spec).strip())
                        if m:
                            add("npm", name, m.group(1), f.path)
            elif base == "go.mod":
                for m in re.finditer(r"^\s*(?:require\s+)?([\w.\-/]+\.[\w.\-/]+)\s+v([\w.+-]+)", f.text, re.M):
                    add("Go", m.group(1), m.group(2), f.path)
            elif base == "gemfile.lock":
                for m in re.finditer(r"^ {4}([\w-]+) \(([\d][\w.]*)\)", f.text, re.M):
                    add("RubyGems", m.group(1), m.group(2), f.path)
            elif base == "composer.lock":
                data = json.loads(f.text)
                for section in ("packages", "packages-dev"):
                    for spec in data.get(section) or []:
                        add("Packagist", spec.get("name", ""), str(spec.get("version", "")), f.path)
        except (ValueError, AttributeError, TypeError):
            continue  # a manifest we cannot parse is skipped, not fatal
    return list(found.values())


_OSV = "https://api.osv.dev/v1"
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _advisory_severity(vuln: dict) -> str | None:
    word = str((vuln.get("database_specific") or {}).get("severity", "")).lower()
    return {"critical": "critical", "high": "high", "moderate": "medium", "medium": "medium", "low": "low"}.get(word)


def _fixed_versions(vuln: dict, package: Package) -> list[str]:
    fixed = []
    for affected in vuln.get("affected") or []:
        if str((affected.get("package") or {}).get("name", "")).lower() != package.name.lower():
            continue
        for rng in affected.get("ranges") or []:
            fixed += [e["fixed"] for e in rng.get("events") or [] if e.get("fixed")]
    return sorted(set(fixed))


async def check_dependencies(packages: list[Package], depth: str = "standard") -> tuple[list[dict], dict]:
    """
    Look each package version up in the OSV database (osv.dev). Only names and
    versions are sent. Returns (findings, a note on what was and was not checked).
    """
    limit = DEPTH_PACKAGES.get(depth, DEPTH_PACKAGES["standard"])
    checked = packages[:limit]
    note = {"packages_found": len(packages), "packages_checked": 0, "vulnerable": 0, "status": "none"}
    if not checked:
        return [], note

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            hits: list[tuple[Package, list[str]]] = []
            for start in range(0, len(checked), 500):
                chunk = checked[start:start + 500]
                r = await client.post(f"{_OSV}/querybatch", json={"queries": [
                    {"package": {"ecosystem": p.ecosystem, "name": p.name}, "version": p.version} for p in chunk
                ]})
                r.raise_for_status()
                for package, result in zip(chunk, r.json().get("results", [])):
                    ids = [v["id"] for v in (result or {}).get("vulns") or [] if v.get("id")]
                    if ids:
                        hits.append((package, ids))

            # Details (summary, severity, fixed version) for the advisories that matched.
            wanted = list(dict.fromkeys(i for _, ids in hits for i in ids))[:300]
            gate = asyncio.Semaphore(10)

            async def detail(vuln_id: str) -> tuple[str, dict]:
                async with gate:
                    try:
                        r = await client.get(f"{_OSV}/vulns/{vuln_id}")
                        return vuln_id, r.json() if r.status_code == 200 else {}
                    except (httpx.HTTPError, ValueError):
                        return vuln_id, {}

            details = dict(await asyncio.gather(*(detail(i) for i in wanted)))
    except (httpx.HTTPError, ValueError) as e:
        note.update(
            status="unavailable", detail=type(e).__name__,
            reason="The vulnerability database (osv.dev) could not be reached, so dependencies were not checked. Run the scan again later.",
        )
        return [], note

    findings = []
    for package, ids in hits:
        vulns = [details.get(i) or {"id": i} for i in ids]
        rated = [s for s in (_advisory_severity(v) for v in vulns) if s]
        severity = min(rated, key=_SEVERITY_RANK.get) if rated else "medium"
        fixes = sorted({f for v in vulns for f in _fixed_versions(v, package)})
        listed = "\n".join(
            f"{v.get('id', '?')}: {(v.get('summary') or 'No summary published').strip()[:160]}" for v in vulns[:6]
        ) + (f"\n…and {len(vulns) - 6} more" if len(vulns) > 6 else "")
        count = len(vulns)
        findings.append(_finding(
            "dependency", severity,
            f"{package.name} {package.version} has {count} known {'vulnerability' if count == 1 else 'vulnerabilities'}",
            f"This project uses {package.name} {package.version} ({package.ecosystem}), which has published security advisories."
            + ("" if rated else " The advisories carry no severity rating, so this is shown as medium."),
            package.manifest, listed,
            (f"Upgrade {package.name}. Versions with fixes: {', '.join(fixes[:8])}." if fixes else f"Upgrade {package.name} to the latest release, or replace it if no fix exists."),
            "CWE-1395", "A06:2021 Vulnerable and Outdated Components",
        ))
    findings.sort(key=lambda f: _SEVERITY_RANK[f["severity"]])
    note.update(packages_checked=len(checked), vulnerable=len(findings), status="checked")
    if len(packages) > len(checked):
        note["reason"] = f"Checked the first {len(checked)} of {len(packages)} packages. Choose a deeper scan to check them all."
    return findings, note


# ---------------------------------------------------------------------------
# Routes and test coverage
# ---------------------------------------------------------------------------

_ROUTE_PATTERNS: list[tuple[tuple[str, ...], re.Pattern]] = [
    # FastAPI, Flask, Sanic: @router.get("/x")
    (_PY, re.compile(r"@\w+(?:\.\w+)*\.(get|post|put|patch|delete)\(\s*[\"']([^\"']*)[\"']", re.I)),
    # Flask: @app.route("/x", methods=["POST"])
    (_PY, re.compile(r"@\w+\.(route)\(\s*[\"']([^\"']+)[\"']", re.I)),
    # Django: path("x/", view)
    (_PY, re.compile(r"\b(?:re_)?(path)\(\s*r?[\"']([^\"']*)[\"']\s*,")),
    # Express, Koa, Fastify, Hono: router.get("/x", ...)
    (_JS, re.compile(r"\b(?:app|router|server|api|route|fastify)\.(get|post|put|patch|delete)\(\s*[\"'`](/[^\"'`]*)[\"'`]", re.I)),
    # Spring: @GetMapping("/x")
    (_JVM, re.compile(r"@(Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*|path\s*=\s*)?\"([^\"]*)\"")),
    # Go: http.HandleFunc("/x", ...), r.GET("/x", ...)
    ((".go",), re.compile(r"\.(HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE)\(\s*\"(/[^\"]*)\"")),
    # Laravel: Route::get('/x', ...)
    ((".php",), re.compile(r"Route::(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']", re.I)),
]
_VERBS = {"get", "post", "put", "patch", "delete"}


def find_routes(files: list[SourceFile]) -> list[dict]:
    routes: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for f in files:
        if f.is_test or not f.language:
            continue
        ext = os.path.splitext(f.path.lower())[1]
        prefix = ""
        if ext == ".py":  # APIRouter(prefix="/x") and Blueprint(url_prefix="/x")
            m = re.search(r"(?:APIRouter|Blueprint)\([^)]*(?:url_)?prefix\s*=\s*[\"']([^\"']+)[\"']", f.text)
            prefix = m.group(1) if m else ""
        prose = _prose_lines(f)
        for number, line in enumerate(f.lines, 1):
            if number in prose or _COMMENT.match(line):
                continue
            for exts, pattern in _ROUTE_PATTERNS:
                if ext not in exts:
                    continue
                m = pattern.search(line)
                if not m:
                    continue
                verb = m.group(1).lower()
                method = verb.upper() if verb in _VERBS else "ANY"
                path = m.group(2)
                if method == "ANY" and pattern.pattern.startswith(r"\b(?:re_)?(path)"):
                    path = "/" + path.lstrip("^/")
                path = (prefix.rstrip("/") + "/" + path.lstrip("/")) if prefix else path
                path = (path.rstrip("/") if prefix and m.group(2) in ("", "/") else path) or "/"
                key = (method, path, f.path)
                if key not in seen:
                    seen.add(key)
                    routes.append({"method": method, "path": path, "file": f.path, "line": number})
                break
        # File-based routing: Next.js pages/ and app/
        m = re.search(r"(?:^|/)(?:src/)?(pages|app)/(.+?)\.(?:[jt]sx?)$", f.path)
        if m and ext in _JS and not re.search(r"(^|/)_(app|document)|(^|/)(components|lib|utils|hooks|api/_)", m.group(2)):
            kind, rest = m.group(1), m.group(2)
            if kind == "app" and not re.search(r"(^|/)(page|route)$", rest):
                continue
            route = "/" + re.sub(r"(^|/)(index|page|route)$", "", rest).strip("/")
            key = ("ANY", route, f.path)
            if key not in seen:
                seen.add(key)
                routes.append({"method": "ANY", "path": route, "file": f.path, "line": 1})
    return routes


def _static_part(path: str) -> str:
    """The longest fixed piece of a route, for matching against test code: /users/{id}/orders -> /orders."""
    pieces = [p for p in re.split(r"\{[^}]*\}|:[A-Za-z_]\w*|<[^>]*>|\[[^\]]*\]", path) if p.strip("/")]
    return max(pieces, key=len).rstrip("/") if pieces else ""


def find_qa_gaps(files: list[SourceFile], routes: list[dict]) -> dict:
    """
    Which source files and routes no test refers to. This compares names and
    text; it does not run the tests, so it shows where tests are missing, not
    how good the existing ones are.
    """
    tests = [f for f in files if f.is_test and f.language]
    source = [f for f in files if f.language and not f.is_test]
    test_text = "\n".join(t.text for t in tests)
    test_names = " ".join(os.path.basename(t.path).lower() for t in tests)

    untested = []
    for f in source:
        stem = os.path.splitext(os.path.basename(f.path))[0]
        if stem.lower() in ("__init__", "index", "main", "setup", "conftest", "manage") or len(f.lines) < 5:
            continue
        if stem.lower() in test_names or re.search(rf"\b{re.escape(stem)}\b", test_text):
            continue
        untested.append({"path": f.path, "lines": len(f.lines), "language": f.language})
    untested.sort(key=lambda u: -u["lines"])

    counted = [f for f in source if len(f.lines) >= 5]
    for route in routes:
        piece = _static_part(route["path"])
        route["tested"] = bool(piece and len(piece) > 1 and piece in test_text)
    untested_routes = [r for r in routes if not r["tested"]]

    covered = len(counted) - len(untested)
    return {
        "source_files": len(source),
        "test_files": len(tests),
        "files_with_tests": max(covered, 0),
        "coverage_pct": round(100 * covered / len(counted)) if counted else None,
        "untested_files": untested[:200],
        "untested_file_count": len(untested),
        "untested_routes": untested_routes[:200],
        "untested_route_count": len(untested_routes),
        "route_count": len(routes),
    }


# ---------------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------------

@dataclass
class CodeScan:
    files_scanned: int = 0
    truncated: bool = False
    languages: dict[str, int] = field(default_factory=dict)
    routes: list[dict] = field(default_factory=list)
    qa_gaps: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    packages: list[Package] = field(default_factory=list)


def scan_tree(root: str, depth: str = "standard", with_security: bool = True) -> CodeScan:
    """Everything that needs no network. Blocking; call it from a worker thread."""
    files, truncated = read_tree(root, depth)
    if not any(f.language for f in files):
        raise SourceError("No source code in a supported language was found")
    languages: dict[str, int] = {}
    for f in files:
        if f.language:
            languages[f.language] = languages.get(f.language, 0) + 1
    routes = find_routes(files)
    scan = CodeScan(
        files_scanned=len(files), truncated=truncated,
        languages=dict(sorted(languages.items(), key=lambda kv: -kv[1])),
        routes=routes, qa_gaps=find_qa_gaps(files, routes),
    )
    if with_security:
        scan.findings = find_secrets(files) + find_risky_code(files) + find_config_problems(files)
        scan.findings.sort(key=lambda f: _SEVERITY_RANK.get(f["severity"], 9))
        scan.packages = find_packages(files)
    return scan


def prepare_source(source_type: str, zip_path: str | None, repo_url: str | None, ref: str | None = None, token: str | None = None) -> str:
    """Put the code in a fresh temporary folder and return its path. The caller deletes it."""
    work = tempfile.mkdtemp(prefix="wiseflow-src-")
    try:
        if source_type == "repo":
            if not repo_url:
                raise SourceError("No repository link was given")
            clone_repo(repo_url, os.path.join(work, "src"), ref=ref, token=token)
        else:
            if not zip_path or not os.path.exists(zip_path):
                raise SourceError("The uploaded code could not be found. Upload it again.")
            os.makedirs(os.path.join(work, "src"))
            extract_zip(zip_path, os.path.join(work, "src"))
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return work


# ---------------------------------------------------------------------------
# Manual test cases from the routes
# ---------------------------------------------------------------------------

CODE_TEST_PROMPT = """You are a senior QA engineer. Below are HTTP routes found by reading an application's source code.
Write manual test cases a tester can follow against a running copy of the app.

Application: {app}
Languages: {languages}
Routes (method, path, source file):
{routes}

Write up to {limit} test cases covering the most important routes: the main success path, invalid input,
and access without signing in where that applies. Do not invent routes that are not listed.

Return ONLY a JSON array. Each item:
{{"title": str, "category": "functional"|"negative"|"security", "priority": "high"|"medium"|"low",
  "preconditions": str, "steps": [str, ...], "expected_result": str, "route": "METHOD /path"}}"""


def _template_cases(routes: list[dict], limit: int) -> list[dict]:
    """Plain cases written without AI, used when the AI service is not available."""
    cases = []
    for r in routes[:limit]:
        name = f"{r['method']} {r['path']}" if r["method"] != "ANY" else r["path"]
        changes = r["method"] in ("POST", "PUT", "PATCH", "DELETE")
        cases.append({
            "title": f"{name} works with valid input",
            "category": "functional", "priority": "high" if changes else "medium",
            "preconditions": "The app is running in a test environment and you are signed in if the route needs it.",
            "steps": [f"Send a valid request to {name}." if r["method"] != "ANY" else f"Open {r['path']}.",
                      "Check the status and the returned content."],
            "expected_result": "The request succeeds and the response matches what the feature should do.",
            "route": name,
        })
        if changes:
            cases.append({
                "title": f"{name} rejects missing or invalid input",
                "category": "negative", "priority": "medium",
                "preconditions": "The app is running in a test environment.",
                "steps": [f"Send {name} with a required field missing.", f"Send {name} with a field of the wrong type."],
                "expected_result": "Each request is refused with a clear validation error and nothing is saved.",
                "route": name,
            })
    return cases[:limit]


async def generate_code_test_cases(scan: CodeScan, app: str, depth: str = "standard") -> tuple[list[dict], str | None]:
    """Manual test cases for the routes found. Returns (cases, a note when AI was not used)."""
    if not scan.routes:
        return [], "No HTTP routes were recognised in this code, so there was nothing to write test cases for."
    limit = {"quick": 12, "standard": 30, "deep": 60}.get(depth, 30)
    # Untested routes first: that is where a tester's time helps most.
    ordered = sorted(scan.routes, key=lambda r: (r.get("tested", False), r["path"]))
    note = None
    cases: list[dict] = []
    try:
        from app.core.ai import ai_client

        ai = ai_client("Code test cases")
        msg = await ai.messages.create(
            model="claude-haiku-4-5", max_tokens=8000,
            messages=[{"role": "user", "content": CODE_TEST_PROMPT.format(
                app=app, languages=", ".join(scan.languages) or "unknown", limit=limit,
                routes="\n".join(f"{r['method']} {r['path']}  ({r['file']})" for r in ordered[:120]),
            )}],
        )
        text = re.sub(r"^```[a-z]*\n?|\n?```$", "", msg.content[0].text.strip())
        parsed = json.loads(text)
        cases = [c for c in parsed if isinstance(c, dict) and c.get("title")][:limit]
    except Exception:
        cases = []
    if not cases:
        cases = _template_cases(ordered, limit)
        note = "The AI service was not available, so these are basic cases built from the route list."
    for number, case in enumerate(cases, 1):
        case["id"] = f"TC-{number:03d}"
        case["page_url"] = case.pop("route", "") or ""
        case["steps"] = [str(s) for s in case.get("steps") or []]
    return cases, note
