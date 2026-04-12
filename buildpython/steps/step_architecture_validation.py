from __future__ import annotations

import re
from collections import Counter

from ..utils.paths import buildlog_dir, repo_root
from ..utils.subproc import RunResult
from .architecture_validation import load_architecture_rules, scan_architecture
from .reports import write_csv, write_json, write_md


_ARCHITECTURE_VALIDATION_RUNTIME_ERRORS = (OSError, ValueError, re.error)


def architecture_validation_runner() -> RunResult:
    root = repo_root()
    report_dir = buildlog_dir()
    config_path = root / "buildpython" / "config" / "architecture_rules.json"

    report_json = report_dir / "architecture-validation.json"
    report_csv = report_dir / "architecture-validation.csv"
    report_md = report_dir / "architecture-validation.md"

    try:
        rules = load_architecture_rules(config_path)
        result = scan_architecture(root, rules)
    except _ARCHITECTURE_VALIDATION_RUNTIME_ERRORS as exc:
        return RunResult(
            command_str="(internal) architecture validation",
            stdout="Architecture validation\n\nFailed to load rules or scan the repo.\n",
            stderr=f"{exc}\n",
            exit_code=1,
        )

    severity_counts = Counter(finding.severity for finding in result.findings)
    rule_counts = Counter(finding.rule_id for finding in result.findings)

    json_payload = {
        "summary": {
            "rules_checked": result.rules_checked,
            "scanned_files": result.scanned_files,
            "findings": len(result.findings),
            "errors": severity_counts.get("error", 0),
            "warnings": severity_counts.get("warning", 0),
        },
        "rules": [
            {
                "id": rule.rule_id,
                "description": rule.description,
                "severity": rule.severity,
                "corpus": {
                    "include": list(rule.include_globs),
                    "exclude": list(rule.exclude_globs),
                },
                "patterns": [
                    {
                        "regex": pattern.regex,
                        "flags": pattern.flags,
                        "message": pattern.message,
                    }
                    for pattern in rule.patterns
                ],
            }
            for rule in rules
        ],
        "findings": [
            {
                "rule_id": finding.rule_id,
                "severity": finding.severity,
                "path": finding.path,
                "line": finding.line,
                "message": finding.message,
                "snippet": finding.snippet,
                "regex": finding.regex,
            }
            for finding in result.findings
        ],
    }
    write_json(report_json, json_payload)

    write_csv(
        report_csv,
        ["severity", "rule_id", "path", "line", "message", "snippet"],
        [
            [
                finding.severity,
                finding.rule_id,
                finding.path,
                str(finding.line),
                finding.message,
                finding.snippet,
            ]
            for finding in result.findings
        ],
    )

    md_lines = [
        "# Architecture validation",
        "",
        f"Rules checked: {result.rules_checked}",
        f"Scanned files: {result.scanned_files}",
        f"Findings: {len(result.findings)}",
        f"Errors: {severity_counts.get('error', 0)}",
        f"Warnings: {severity_counts.get('warning', 0)}",
        "",
    ]
    if result.findings:
        md_lines.extend(
            [
                "## Findings",
                "",
                "| Severity | Rule | Path | Line | Message |",
                "|---|---|---|---:|---|",
            ]
        )
        for finding in result.findings[:200]:
            md_lines.append(
                f"| {finding.severity} | {finding.rule_id} | {finding.path} | {finding.line} | {finding.message} |"
            )
    else:
        md_lines.append("No architecture violations detected.")
    write_md(report_md, md_lines)

    stdout_lines = [
        "Architecture validation",
        "",
        f"Rules checked: {result.rules_checked}",
        f"Scanned files: {result.scanned_files}",
        f"Errors: {severity_counts.get('error', 0)} | Warnings: {severity_counts.get('warning', 0)}",
    ]

    if result.findings:
        stdout_lines.append("")
        stdout_lines.append("Findings:")
        for finding in result.findings[:50]:
            stdout_lines.append(
                f"  [{finding.severity.upper()}] {finding.path}:{finding.line} {finding.rule_id} - {finding.message}"
            )
        if len(result.findings) > 50:
            stdout_lines.append(f"  ... {len(result.findings) - 50} more findings")
        stdout_lines.append("")
        stdout_lines.append("Rule totals:")
        for rule_id, count in sorted(rule_counts.items()):
            stdout_lines.append(f"  - {rule_id}: {count}")
    else:
        stdout_lines.append("")
        stdout_lines.append("No architecture violations detected.")

    exit_code = 1 if severity_counts.get("error", 0) > 0 else 0
    return RunResult(
        command_str="(internal) architecture validation",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )
