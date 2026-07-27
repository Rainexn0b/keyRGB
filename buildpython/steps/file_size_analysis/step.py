from __future__ import annotations

import json
from pathlib import Path

from ...utils.paths import repo_root
from ...utils.subproc import RunResult
from .constants import SIZE_SCAN_ROOTS
from .report_content._shared import delegation_count, file_counts, import_counts, middleman_count, unreferenced_count
from .reporting import build_stdout_lines, write_reports
from .scanning import collect_hotspots

_DEBT_BASELINE_PATH = Path("buildpython/config/debt_baselines.json")


def _load_structure_baseline(root: Path) -> dict[str, int]:
    try:
        payload = json.loads((root / _DEBT_BASELINE_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    section = payload.get("file_size_analysis", {})
    counts = section.get("counts", {}) if isinstance(section, dict) else {}
    return {str(key): int(value) for key, value in counts.items() if isinstance(value, int | float)}


def _structure_regressions(current: dict[str, int], baseline: dict[str, int]) -> list[tuple[str, int, int]]:
    return [
        (category, current.get(category, 0), expected)
        for category, expected in sorted(baseline.items())
        if current.get(category, 0) > expected
    ]


def file_size_runner() -> RunResult:
    root = repo_root()
    (
        file_rows,
        import_rows,
        flat_directories,
        flat_directories_allowed,
        delegation_rows,
        middleman_rows,
        unreferenced_rows,
        waiver_rows,
    ) = collect_hotspots(root, roots=SIZE_SCAN_ROOTS)
    write_reports(
        root=root,
        file_rows=file_rows,
        import_rows=import_rows,
        flat_directories=flat_directories,
        flat_directories_allowed=flat_directories_allowed,
        delegation_rows=delegation_rows,
        middleman_rows=middleman_rows,
        unreferenced_rows=unreferenced_rows,
        waiver_rows=waiver_rows,
    )
    stdout = "\n".join(
        build_stdout_lines(
            file_rows=file_rows,
            import_rows=import_rows,
            flat_directories=flat_directories,
            flat_directories_allowed=flat_directories_allowed,
            delegation_rows=delegation_rows,
            middleman_rows=middleman_rows,
            unreferenced_rows=unreferenced_rows,
            waiver_rows=waiver_rows,
        )
    )
    current_counts = {
        "large_files": file_counts(file_rows)["total"],
        "long_import_blocks": import_counts(import_rows)["total"],
        "flat_directories": len(flat_directories),
        "delegation_candidates": delegation_count(delegation_rows),
        "middleman_modules": middleman_count(middleman_rows),
        "unreferenced_files": unreferenced_count(unreferenced_rows),
    }
    regressions = _structure_regressions(current_counts, _load_structure_baseline(root))
    if regressions:
        stdout += "\n\nStructural regressions:\n" + "\n".join(
            f"  {category}: current={current} baseline={expected}" for category, current, expected in regressions
        )
    return RunResult(
        command_str="(internal) file size analysis",
        stdout=stdout + "\n",
        stderr="",
        exit_code=1 if regressions else 0,
    )
