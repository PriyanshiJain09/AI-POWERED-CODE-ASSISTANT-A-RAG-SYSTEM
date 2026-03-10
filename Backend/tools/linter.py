# tools/linter.py — Run ruff (linter) or semgrep (security scanner)

import os
import json
import asyncio
import tempfile
import subprocess
from github_client import get_file_content, list_repo_files

SUPPORTED_SCAN_TYPES = {"lint", "semgrep"}


async def run_scan(repo_full: str, file_path: str, scan_type: str) -> list[dict]:
    """
    Run a lint or security scan.
    - If file_path is given, scans just that file.
    - If empty, scans all Python files in the repo (up to 20 files).
    """
    if scan_type not in SUPPORTED_SCAN_TYPES:
        return [{"severity": "error", "message": f"Unknown scan type: {scan_type}"}]

    # Gather files to scan
    if file_path:
        content = await get_file_content(repo_full, file_path)
        if not content:
            return [{"severity": "error", "message": f"File not found: {file_path}"}]
        files_to_scan = {file_path: content}
    else:
        # Scan up to 20 Python/JS files
        all_files = await list_repo_files(repo_full, extensions=[".py", ".js", ".ts"])
        all_files = all_files[:20]
        from github_client import get_file_batch
        files_to_scan = await get_file_batch(repo_full, [f["path"] for f in all_files])

    if not files_to_scan:
        return []

    # Write files to a temp directory and scan
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write all files preserving directory structure
        for path, content in files_to_scan.items():
            full_path = os.path.join(tmpdir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(content)

        if scan_type == "lint":
            return await _run_ruff(tmpdir, files_to_scan)
        else:
            return await _run_semgrep(tmpdir, files_to_scan)


async def _run_ruff(tmpdir: str, files: dict) -> list[dict]:
    """Run ruff linter. Falls back to basic checks if ruff isn't installed."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ruff", "check", tmpdir, "--output-format=json", "--no-cache",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        raw = json.loads(stdout.decode()) if stdout else []
        return [_normalise_ruff(r) for r in raw]

    except FileNotFoundError:
        # ruff not installed — do a basic manual check
        return _basic_lint(files)


async def _run_semgrep(tmpdir: str, files: dict) -> list[dict]:
    """Run semgrep security scan. Falls back to pattern matching if not installed."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "semgrep", "scan", tmpdir,
            "--config=auto",
            "--json",
            "--quiet",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout.decode()) if stdout else {}
        results = data.get("results", [])
        return [_normalise_semgrep(r) for r in results]

    except FileNotFoundError:
        # semgrep not installed — run basic security pattern checks
        return _basic_security_check(files)


def _normalise_ruff(r: dict) -> dict:
    return {
        "severity": "warning" if r.get("noqa") else "error",
        "file":     r.get("filename", "").split("/")[-1],
        "line":     r.get("location", {}).get("row", 0),
        "message":  r.get("message", ""),
        "rule":     r.get("code", ""),
    }


def _normalise_semgrep(r: dict) -> dict:
    severity_map = {"ERROR": "error", "WARNING": "warning", "INFO": "info"}
    return {
        "severity": severity_map.get(r.get("extra", {}).get("severity", "INFO"), "info"),
        "file":     r.get("path", "").split("/")[-1],
        "line":     r.get("start", {}).get("line", 0),
        "message":  r.get("extra", {}).get("message", ""),
        "rule":     r.get("check_id", ""),
    }


def _basic_lint(files: dict) -> list[dict]:
    """Very basic lint checks when ruff isn't available."""
    import ast
    issues = []
    for path, content in files.items():
        if not path.endswith(".py"):
            continue
        try:
            ast.parse(content)
        except SyntaxError as e:
            issues.append({
                "severity": "error",
                "file": path.split("/")[-1],
                "line": e.lineno or 0,
                "message": f"Syntax error: {e.msg}",
                "rule": "syntax-error",
            })
        # Check for obvious issues
        for i, line in enumerate(content.splitlines(), 1):
            if "print(" in line and not path.endswith("test"):
                issues.append({
                    "severity": "warning",
                    "file": path.split("/")[-1],
                    "line": i,
                    "message": "Consider using logging instead of print()",
                    "rule": "no-print",
                })
            if "TODO" in line or "FIXME" in line:
                issues.append({
                    "severity": "info",
                    "file": path.split("/")[-1],
                    "line": i,
                    "message": line.strip(),
                    "rule": "todo-comment",
                })
    return issues[:30]  # cap at 30


def _basic_security_check(files: dict) -> list[dict]:
    """Basic security pattern matching when semgrep isn't available."""
    import re
    issues = []

    patterns = [
        (r"eval\(", "error", "Dangerous use of eval()", "no-eval"),
        (r"exec\(", "error", "Dangerous use of exec()", "no-exec"),
        (r"subprocess\.call\(.*shell=True", "error", "shell=True is a command injection risk", "no-shell-true"),
        (r"password\s*=\s*['\"]", "error", "Hardcoded password detected", "no-hardcoded-password"),
        (r"secret\s*=\s*['\"]", "error", "Hardcoded secret detected", "no-hardcoded-secret"),
        (r"api_key\s*=\s*['\"]", "warning", "Hardcoded API key detected", "no-hardcoded-apikey"),
        (r"SELECT .* FROM .* WHERE .*%s", "error", "Possible SQL injection (string formatting)", "sql-injection"),
        (r"\.format\(.*\).*WHERE", "warning", "Possible SQL injection (.format)", "sql-injection-format"),
        (r"pickle\.loads\(", "warning", "Unsafe pickle deserialization", "no-pickle-loads"),
        (r"http://", "info", "Non-HTTPS URL detected", "use-https"),
    ]

    for path, content in files.items():
        for i, line in enumerate(content.splitlines(), 1):
            for pattern, severity, message, rule in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        "severity": severity,
                        "file": path.split("/")[-1],
                        "line": i,
                        "message": message,
                        "rule": f"security/{rule}",
                    })

    return issues[:30]
