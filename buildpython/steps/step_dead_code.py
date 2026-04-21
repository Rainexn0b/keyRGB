from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..utils.paths import buildlog_dir, repo_root
from ..utils.subproc import RunResult, python_exe, run


_FINDING_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+): (?P<message>.+) \((?P<confidence>\d+)% confidence\)$"
)
_SCAN_ROOTS = ("src", "buildpython", "tests")
_MIN_CONFIDENCE = 80


def _scope_for_path(path: str) -> str:
    if path.startswith("src/core/"):
        return "src/core"
    if path.startswith("src/gui/"):
        return "src/gui"
    if path.startswith("src/tray/"):
        return "src/tray"
    if path.startswith("src/"):
        return "src/other"
    if path.startswith("buildpython/"):
        return "buildpython"
    if path.startswith("tests/"):
        return "tests"
    return "other"


def _parse_findings(stdout: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _FINDING_RE.match(line)
        if not match:
            continue
        path = match.group("path")
        findings.append(
            {
                "path": path,
                "line": int(match.group("line")),
                "message": match.group("message"),
                "confidence": int(match.group("confidence")),
                "scope": _scope_for_path(path),
            }
        )
    findings.sort(key=lambda item: (-int(item["confidence"]), str(item["path"]), int(item["line"])))
    return findings


def _counts_by_scope(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in findings:
        scope = str(item.get("scope", "other"))
        counts[scope] = counts.get(scope, 0) + 1
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def _write_reports(*, report_dir: Path, findings: list[dict[str, Any]], raw_output: str) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)

    (report_dir / "dead-code-vulture.txt").write_text(raw_output, encoding="utf-8")

    payload = {
        "tool": "vulture",
        "scan_roots": list(_SCAN_ROOTS),
        "min_confidence": _MIN_CONFIDENCE,
        "count": len(findings),
        "counts_by_scope": _counts_by_scope(findings),
        "findings": findings,
    }
    (report_dir / "dead-code-vulture.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md_lines = [
        "# Dead code scan",
        "",
        "- Tool: `vulture`",
        f"- Scope: {', '.join(_SCAN_ROOTS)}",
        f"- Minimum confidence: {_MIN_CONFIDENCE}%",
        f"- Findings: {len(findings)}",
        "",
        "## By scope",
        "",
    ]

    counts = _counts_by_scope(findings)
    if not counts:
        md_lines.append("No findings.")
    else:
        md_lines.extend(f"- {scope}: {count}" for scope, count in counts.items())

    md_lines.extend(["", "## Top findings", "", "| Confidence | Path | Line | Message |", "|---:|---|---:|---|"])
    for item in findings[:120]:
        md_lines.append(
            f"| {int(item['confidence'])}% | {item['path']} | {int(item['line'])} | {item['message']} |"
        )

    (report_dir / "dead-code-vulture.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def dead_code_runner() -> RunResult:
    root = repo_root()
    args = [
        python_exe(),
        "-m",
        "vulture",
        *_SCAN_ROOTS,
        "--min-confidence",
        str(_MIN_CONFIDENCE),
    ]

    result = run(
        args,
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )

    # Vulture uses 3 when findings are present; keep this step informational.
    if result.exit_code not in {0, 3}:
        return result

    findings = _parse_findings(result.stdout)
    _write_reports(report_dir=buildlog_dir(), findings=findings, raw_output=result.stdout)

    stdout_lines = [
        "Dead code scan (vulture)",
        "",
        f"Scan roots: {', '.join(_SCAN_ROOTS)}",
        f"Minimum confidence: {_MIN_CONFIDENCE}%",
        f"Findings: {len(findings)}",
    ]

    counts = _counts_by_scope(findings)
    if counts:
        stdout_lines.append("")
        stdout_lines.append("By scope:")
        stdout_lines.extend(f"  - {scope}: {count}" for scope, count in counts.items())

    if findings:
        stdout_lines.append("")
        stdout_lines.append("Top findings:")
        for item in findings[:80]:
            stdout_lines.append(
                f"  - {int(item['confidence'])}% {item['path']}:{int(item['line'])} {item['message']}"
            )

    return RunResult(
        command_str=result.command_str,
        stdout="\n".join(stdout_lines) + "\n",
        stderr=result.stderr,
        exit_code=0,
    )
