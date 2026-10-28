"""
Playwright test runner — executes generated Python test code in a subprocess,
captures stdout/stderr, returns structured results.
"""
import subprocess
import os
import time
import json
from pathlib import Path
import tempfile


def run_playwright_tests(code: str) -> dict:
    """
    Write generated code to a temp file, run with pytest-playwright,
    parse results. Returns dict with status, duration_ms, stdout, error.
    """
    start = time.time()
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_generated.py"
        test_file.write_text(code)

        result = subprocess.run(
            ["python", "-m", "pytest", str(test_file), "-v", "--tb=short",
             "--json-report", "--json-report-file=report.json",
             "--screenshot=only-on-failure", f"--output={tmpdir}/screenshots"],
            capture_output=True, text=True, timeout=120, cwd=tmpdir,
            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright"}
        )

        duration_ms = int((time.time() - start) * 1000)
        stdout = (result.stdout + "\n" + result.stderr).strip()

        report_path = Path(tmpdir) / "report.json"
        tests_total = tests_passed = tests_failed = 0
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text())
                summary = report.get("summary", {})
                tests_total = summary.get("total", 0)
                tests_passed = summary.get("passed", 0)
                tests_failed = summary.get("failed", 0)
            except Exception:
                pass

        passed = result.returncode == 0
        return {
            "passed": passed,
            "duration_ms": duration_ms,
            "stdout": stdout[:10000],
            "error": "" if passed else stdout[-2000:],
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
        }
