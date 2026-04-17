"""Exception transparency debt scan.

Tracks broad exception patterns that hide failures or make them harder to
diagnose in production. Fails on naked/BaseException catches (always wrong);
other broad-except categories are gated at zero via GATED_CATEGORIES.
"""

from __future__ import annotations

from collections import Counter

from ...utils.paths import repo_root
from ...utils.subproc import RunResult
from .reporting import build_stdout, write_reports
from .scanner import collect_annotation_inventory, collect_findings, count_broad_waivers
from .scanner import scan_python_source as _scan_python_source


GATED_CATEGORIES = {"naked_except", "baseexception_catch"}


def exception_transparency_runner() -> RunResult:
    root = repo_root()
    findings = collect_findings(root)
    waived_total = count_broad_waivers(root)
    annotation_inventory = collect_annotation_inventory(root)

    counts: Counter[str] = Counter()
    for finding in findings:
        counts[finding.category] += 1

    stdout_lines = build_stdout(findings, counts, waived_total, annotation_inventory)
    write_reports(root, findings, counts, waived_total, annotation_inventory)

    should_fail = any(counts.get(cat, 0) > 0 for cat in GATED_CATEGORIES)
    return RunResult(
        command_str="(internal) exception transparency check",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=1 if should_fail else 0,
    )
