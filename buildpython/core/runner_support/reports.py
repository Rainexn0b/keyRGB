"""Associate displayed metrics with artifacts produced by this step invocation."""

from __future__ import annotations

from pathlib import Path

STEP_REPORTS = {
    "Code Markers": "code-markers.json",
    "File Size": "file-size-analysis.json",
    "LOC Check": "loc-check.json",
    "Code Hygiene": "code-hygiene.json",
    "Architecture Validation": "architecture-validation.json",
    "Coverage": "coverage-summary.json",
    "Exception Transparency": "exception-transparency.json",
    "Dead Code": "dead-code-vulture.json",
}


def report_stamp(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


def refreshed_reports(directory: Path, step_name: str, before: tuple[int, int] | None) -> tuple[str, ...]:
    name = STEP_REPORTS.get(step_name)
    if name is None:
        return ()
    after = report_stamp(directory / name)
    return (name,) if after is not None and after != before else ()
