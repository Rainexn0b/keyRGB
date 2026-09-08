"""Supply-chain dependency audit wrapper around ``pip-audit``.

Audits runtime requirements declared in ``pyproject.toml`` for ``project-dir``
rather than arbitrary ambient packages installed in the environment.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

EXIT_CLEAN: Final[int] = 0
EXIT_FINDINGS: Final[int] = 1
EXIT_TOOL_ERROR: Final[int] = 2

AUDIT_TIMEOUT_SECONDS: Final[float] = 300.0
AUDIT_FORMAT_ARGS: Final[tuple[str, ...]] = (
    "--format=json",
    "--desc=off",
    "--progress-spinner=off",
    "--vulnerability-service=pypi",
)

VerdictStatus = Literal["clean", "findings", "invalid"]


@dataclass(frozen=True)
class Finding:
    """A single audited package with at least one known vulnerability."""

    package: str
    version: str
    vuln_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuditVerdict:
    """Pure classification result for a parsed pip-audit JSON document."""

    status: VerdictStatus
    findings: tuple[Finding, ...] = ()


def parse_report_text(text: str) -> Any:
    """Parse raw pip-audit stdout into a JSON document.

    Raises:
        ValueError: when stdout is empty or is not valid JSON.
    """
    if not text.strip():
        raise ValueError("empty pip-audit report")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed pip-audit JSON: {exc}") from exc


def _finding_for_dependency(entry: Any) -> Finding | None:
    """Return a Finding when a dependency entry carries vulnerabilities."""
    if not isinstance(entry, dict):
        raise TypeError("dependency entry must be an object")
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("dependency entry is missing a name")
    if "skip_reason" in entry and entry.get("vulns", None) in ([], None):
        skip_reason = entry.get("skip_reason")
        if not isinstance(skip_reason, str) or not skip_reason:
            raise ValueError(f"dependency {name!r} has an invalid skip_reason")
        return None
    vulns = entry.get("vulns")
    if not isinstance(vulns, list):
        raise TypeError(f"dependency {name!r} has a non-list vulns field")
    if not vulns:
        return None
    version = entry.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"dependency {name!r} has an invalid version")
    vuln_ids: list[str] = []
    for vuln in vulns:
        if not isinstance(vuln, dict):
            raise TypeError(f"dependency {name!r} has a malformed vulnerability entry")
        vuln_id = vuln.get("id")
        if not isinstance(vuln_id, str) or not vuln_id:
            raise ValueError(f"dependency {name!r} has a vulnerability without an id")
        vuln_ids.append(vuln_id)
    return Finding(package=name, version=version, vuln_ids=tuple(vuln_ids))


def classify_report(payload: Any) -> AuditVerdict:
    """Classify a parsed pip-audit JSON document without side effects."""
    if not isinstance(payload, dict):
        return AuditVerdict(status="invalid")
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        return AuditVerdict(status="invalid")
    top_level_vulns = payload.get("vulnerabilities", [])
    if "vulnerabilities" in payload and not isinstance(top_level_vulns, list):
        return AuditVerdict(status="invalid")
    findings: list[Finding] = []
    try:
        for entry in dependencies:
            finding = _finding_for_dependency(entry)
            if finding is not None:
                findings.append(finding)
    except (TypeError, ValueError):
        return AuditVerdict(status="invalid")
    if findings:
        return AuditVerdict(status="findings", findings=tuple(findings))
    if isinstance(top_level_vulns, list) and top_level_vulns:
        return AuditVerdict(
            status="findings", findings=(Finding(package="*", version="*", vuln_ids=("vulnerabilities",)),)
        )
    return AuditVerdict(status="clean")


def build_audit_command(python_executable: str, project_dir: str) -> list[str]:
    """Build the hermetic pip-audit invocation for a project directory."""
    return [python_executable, "-m", "pip_audit", project_dir, *AUDIT_FORMAT_ARGS]


def format_findings_diagnostic(verdict: AuditVerdict) -> str:
    """Render the concise stdout diagnostic for a findings verdict."""
    total = sum(len(finding.vuln_ids) for finding in verdict.findings)
    packages = len(verdict.findings)
    details = ", ".join(
        f"{finding.package} {finding.version} ({', '.join(finding.vuln_ids)})" for finding in verdict.findings
    )
    return (
        f"dependency audit: found {total} vulnerabilit{'y' if total == 1 else 'ies'} "
        f"across {packages} package{'s' if packages != 1 else ''}: {details}"
    )


def _stderr_detail(stderr: str) -> str:
    """Return one useful stderr line without flooding CI logs."""
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return f": {lines[-1]}" if lines else ""


def run_audit(project_dir: Path, *, timeout: float = AUDIT_TIMEOUT_SECONDS) -> int:
    """Run pip-audit for project_dir and map the outcome to an exit code."""
    resolved_project_dir = project_dir.resolve()
    if not (resolved_project_dir / "pyproject.toml").is_file():
        print(f"dependency audit failed: no pyproject.toml in {resolved_project_dir}", file=sys.stderr)
        return EXIT_TOOL_ERROR
    if timeout <= 0:
        print("dependency audit failed: timeout must be greater than zero", file=sys.stderr)
        return EXIT_TOOL_ERROR
    command = build_audit_command(sys.executable, str(resolved_project_dir))
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(resolved_project_dir),
        )
    except subprocess.TimeoutExpired:
        print(f"dependency audit failed: pip-audit timed out after {timeout:g}s", file=sys.stderr)
        return EXIT_TOOL_ERROR
    except FileNotFoundError as exc:
        print(f"dependency audit failed: unable to launch pip-audit: {exc}", file=sys.stderr)
        return EXIT_TOOL_ERROR
    except OSError as exc:
        print(f"dependency audit failed: unable to launch pip-audit: {exc}", file=sys.stderr)
        return EXIT_TOOL_ERROR
    try:
        payload = parse_report_text(completed.stdout)
    except ValueError as exc:
        print(f"dependency audit failed: {exc} (pip-audit exit {completed.returncode})", file=sys.stderr)
        return EXIT_TOOL_ERROR
    verdict = classify_report(payload)
    if verdict.status == "invalid":
        print(
            f"dependency audit failed: invalid pip-audit report shape (pip-audit exit {completed.returncode})",
            file=sys.stderr,
        )
        return EXIT_TOOL_ERROR
    if verdict.status == "findings":
        print(format_findings_diagnostic(verdict))
        return EXIT_FINDINGS
    if completed.returncode != 0:
        print(
            f"dependency audit failed: pip-audit exited {completed.returncode} without parseable findings"
            f"{_stderr_detail(completed.stderr)}",
            file=sys.stderr,
        )
        return EXIT_TOOL_ERROR
    print("dependency audit: no known vulnerabilities")
    return EXIT_CLEAN


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the audit wrapper."""
    parser = argparse.ArgumentParser(description="Audit runtime dependencies with pip-audit.")
    parser.add_argument("--project-dir", default=".", help="Project directory containing pyproject.toml")
    parser.add_argument(
        "--timeout",
        type=float,
        default=AUDIT_TIMEOUT_SECONDS,
        help="Subprocess timeout in seconds",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint returning a process exit code."""
    args = parse_args(argv)
    return run_audit(Path(args.project_dir), timeout=args.timeout)


if __name__ == "__main__":
    sys.exit(main())
