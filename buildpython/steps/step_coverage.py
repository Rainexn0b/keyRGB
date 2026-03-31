from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..utils.paths import buildlog_dir, repo_root
from ..utils.subproc import RunResult, python_exe, run
from .reports import write_csv, write_json, write_md


_DEBT_BASELINE_PATH = Path("buildpython/config/debt_baselines.json")
_DATA_FILE_NAME = ".coverage.buildpython"
_RAW_JSON_NAME = "coverage-raw.json"
_SUMMARY_JSON_NAME = "coverage-summary.json"
_SUMMARY_MD_NAME = "coverage-summary.md"
_SUMMARY_CSV_NAME = "coverage-summary.csv"
_CAPTURE_MARKER_NAME = "coverage-capture.json"


@dataclass(frozen=True)
class CoverageBaseline:
    minimum_total_percent: float | None
    tracked_prefixes: dict[str, float]
    watch_files: tuple[str, ...]


@dataclass(frozen=True)
class CoverageRegression:
    kind: str
    target: str
    current: float
    baseline: float


def _coerce_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _coerce_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _lowest_covered_sort_key(item: dict[str, Any]) -> tuple[float, int, str]:
    return (
        _coerce_float(item.get("percent", 0.0)),
        -_coerce_int(item.get("num_statements", 0)),
        str(item.get("path", "")),
    )


def pytest_runner_with_optional_coverage() -> RunResult:
    root = repo_root()
    if _coverage_tool_available():
        return _run_pytest_under_coverage(root=root, reason="pytest-step")

    _clear_coverage_artifacts()
    return run(
        [python_exe(), "-m", "pytest", "-q", "-o", "addopts="],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )


def coverage_runner() -> RunResult:
    root = repo_root()
    report_dir = buildlog_dir()
    baseline = _load_coverage_baseline(root)

    if not _coverage_tool_available():
        return RunResult(
            command_str="(internal) coverage summary",
            stdout="Coverage summary skipped: coverage.py is not installed.\n",
            stderr="",
            exit_code=0,
        )

    if not _has_fresh_pytest_coverage_data():
        _clear_coverage_report_artifacts()
        _write_missing_capture_reports(report_dir=report_dir)
        return RunResult(
            command_str="(internal) coverage summary",
            stdout=(
                "Coverage summary\n\n"
                "No fresh pytest coverage capture was found.\n\n"
                "Run one of:\n"
                "  .venv/bin/python -m buildpython --run-steps=2,18\n"
                "  .venv/bin/python -m buildpython --profile debt\n"
                "  .venv/bin/python -m buildpython --profile full\n"
            ),
            stderr="",
            exit_code=1,
        )

    raw_json_path = report_dir / _RAW_JSON_NAME
    json_result = run(
        [
            python_exe(),
            "-m",
            "coverage",
            "json",
            "--data-file",
            str(_coverage_data_file()),
            "-o",
            str(raw_json_path),
            "--pretty-print",
        ],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
    if json_result.exit_code != 0:
        return RunResult(
            command_str=json_result.command_str,
            stdout="Coverage summary\n\nFailed to export coverage JSON.\n",
            stderr=json_result.stderr,
            exit_code=json_result.exit_code,
        )

    payload = _load_json_file(raw_json_path)
    report = build_coverage_report(payload, baseline)
    _write_coverage_reports(report_dir=report_dir, report=report)

    stdout_lines = _build_stdout(report)
    regressions = report.get("baseline", {}).get("regressions", [])
    exit_code = 1 if regressions else 0
    return RunResult(
        command_str="(internal) coverage summary",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )


def build_coverage_report(payload: dict[str, Any], baseline: CoverageBaseline) -> dict[str, Any]:
    files = _normalize_files(payload)
    totals = _extract_totals(payload)
    total_percent = _percent_from_counts(
        covered=int(totals.get("covered_lines", 0)),
        statements=int(totals.get("num_statements", 0)),
    )

    tracked_prefixes: list[dict[str, Any]] = []
    regressions: list[CoverageRegression] = []
    for prefix, expected in baseline.tracked_prefixes.items():
        aggregate = _aggregate_prefix(files, prefix)
        current_percent = _percent_from_counts(
            covered=int(aggregate.get("covered_lines", 0)),
            statements=int(aggregate.get("num_statements", 0)),
        )
        if current_percent < float(expected):
            regressions.append(
                CoverageRegression(
                    kind="prefix",
                    target=prefix,
                    current=current_percent,
                    baseline=float(expected),
                )
            )
        tracked_prefixes.append(
            {
                "prefix": prefix,
                "percent": round(current_percent, 2),
                "baseline": round(float(expected), 2),
                "delta": round(current_percent - float(expected), 2),
                "covered_lines": int(aggregate.get("covered_lines", 0)),
                "num_statements": int(aggregate.get("num_statements", 0)),
                "status": "fail" if current_percent < float(expected) else "ok",
            }
        )

    minimum_total = baseline.minimum_total_percent
    if minimum_total is not None and total_percent < float(minimum_total):
        regressions.append(
            CoverageRegression(
                kind="total",
                target="total",
                current=total_percent,
                baseline=float(minimum_total),
            )
        )

    watch_file_rows: list[dict[str, Any]] = []
    for rel_path in baseline.watch_files:
        file_summary = files.get(rel_path)
        if file_summary is None:
            watch_file_rows.append(
                {
                    "path": rel_path,
                    "percent": None,
                    "covered_lines": 0,
                    "num_statements": 0,
                    "status": "missing",
                }
            )
            continue
        watch_file_rows.append(
            {
                "path": rel_path,
                "percent": round(float(file_summary.get("percent", 0.0)), 2),
                "covered_lines": int(file_summary.get("covered_lines", 0)),
                "num_statements": int(file_summary.get("num_statements", 0)),
                "status": "ok",
            }
        )

    lowest_covered_rows: list[dict[str, Any]] = []
    for rel_path, item in files.items():
        num_statements = _coerce_int(item.get("num_statements", 0))
        if num_statements <= 0:
            continue
        lowest_covered_rows.append(
            {
                "path": rel_path,
                "percent": round(_coerce_float(item.get("percent", 0.0)), 2),
                "covered_lines": _coerce_int(item.get("covered_lines", 0)),
                "num_statements": num_statements,
            }
        )

    lowest_covered = sorted(lowest_covered_rows, key=_lowest_covered_sort_key)[:20]

    return {
        "summary": {
            "total_percent": round(total_percent, 2),
            "covered_lines": int(totals.get("covered_lines", 0)),
            "num_statements": int(totals.get("num_statements", 0)),
            "files": len(files),
        },
        "baseline": {
            "minimum_total_percent": None if minimum_total is None else round(float(minimum_total), 2),
            "delta_total_percent": None if minimum_total is None else round(total_percent - float(minimum_total), 2),
            "tracked_prefixes": {prefix: round(float(value), 2) for prefix, value in baseline.tracked_prefixes.items()},
            "regressions": [
                {
                    "kind": item.kind,
                    "target": item.target,
                    "current": round(item.current, 2),
                    "baseline": round(item.baseline, 2),
                }
                for item in regressions
            ],
        },
        "tracked_prefixes": tracked_prefixes,
        "watch_files": watch_file_rows,
        "lowest_covered_files": lowest_covered,
    }


def _build_stdout(report: dict[str, Any]) -> list[str]:
    lines = [
        "Coverage summary",
        "",
    ]
    summary = report.get("summary", {})
    baseline = report.get("baseline", {})
    total_percent = float(summary.get("total_percent", 0.0))
    minimum_total = baseline.get("minimum_total_percent")
    delta_total = baseline.get("delta_total_percent")
    baseline_text = "-" if minimum_total is None else f"{float(minimum_total):.2f}%"
    delta_text = "n/a" if delta_total is None else f"{float(delta_total):+.2f}%"
    lines.append(
        f"Total: {total_percent:.2f}%  baseline={baseline_text} delta={delta_text} "
        f"({summary.get('covered_lines', 0)}/{summary.get('num_statements', 0)} lines)"
    )

    tracked_prefixes = report.get("tracked_prefixes", [])
    if isinstance(tracked_prefixes, list) and tracked_prefixes:
        lines.append("")
        lines.append("Tracked prefixes:")
        for item in tracked_prefixes:
            prefix = item.get("prefix")
            percent = item.get("percent")
            expected = item.get("baseline")
            delta = item.get("delta")
            if not isinstance(prefix, str):
                continue
            status = "FAIL" if item.get("status") == "fail" else "OK"
            lines.append(
                f"  {prefix}: {float(percent):.2f}% baseline={float(expected):.2f}% delta={float(delta):+.2f}% [{status}]"
            )

    watch_files = report.get("watch_files", [])
    if isinstance(watch_files, list) and watch_files:
        lines.append("")
        lines.append("Watch files:")
        for item in watch_files:
            path = item.get("path")
            if not isinstance(path, str):
                continue
            percent = item.get("percent")
            if percent is None:
                lines.append(f"  {path}: not present in coverage payload")
                continue
            lines.append(f"  {path}: {float(percent):.2f}%")

    lowest = report.get("lowest_covered_files", [])
    if isinstance(lowest, list) and lowest:
        lines.append("")
        lines.append("Lowest-covered files:")
        for item in lowest[:10]:
            path = item.get("path")
            percent = item.get("percent")
            statements = item.get("num_statements")
            if isinstance(path, str):
                lines.append(f"  {path}: {float(percent):.2f}% ({statements} statements)")

    regressions = baseline.get("regressions", [])
    if isinstance(regressions, list) and regressions:
        lines.append("")
        lines.append("Coverage regressions:")
        for item in regressions:
            kind = item.get("kind")
            target = item.get("target")
            current = item.get("current")
            expected = item.get("baseline")
            if isinstance(kind, str) and isinstance(target, str):
                lines.append(f"  {kind} {target}: {float(current):.2f}% < baseline {float(expected):.2f}%")
    else:
        lines.append("")
        lines.append("Coverage regressions: none")

    lines.append("")
    lines.append(f"Reports: {buildlog_dir() / _SUMMARY_MD_NAME}")
    return lines


def _write_coverage_reports(*, report_dir: Path, report: dict[str, Any]) -> None:
    write_json(report_dir / _SUMMARY_JSON_NAME, report)

    write_csv(
        report_dir / _SUMMARY_CSV_NAME,
        ["path", "percent", "covered_lines", "num_statements", "watched"],
        [
            [
                str(item.get("path", "")),
                "" if item.get("percent") is None else f"{float(item.get('percent', 0.0)):.2f}",
                str(item.get("covered_lines", 0)),
                str(item.get("num_statements", 0)),
                "yes",
            ]
            for item in report.get("watch_files", [])
        ]
        + [
            [
                str(item.get("path", "")),
                f"{float(item.get('percent', 0.0)):.2f}",
                str(item.get("covered_lines", 0)),
                str(item.get("num_statements", 0)),
                "no",
            ]
            for item in report.get("lowest_covered_files", [])
        ],
    )

    summary = report.get("summary", {})
    baseline = report.get("baseline", {})
    md_lines = [
        "# Coverage summary",
        "",
        f"- Total coverage: {float(summary.get('total_percent', 0.0)):.2f}%",
        f"- Covered lines: {summary.get('covered_lines', 0)}",
        f"- Statements: {summary.get('num_statements', 0)}",
        f"- Files: {summary.get('files', 0)}",
        "",
    ]

    minimum_total = baseline.get("minimum_total_percent")
    if minimum_total is not None:
        md_lines.append(f"- Baseline total: {float(minimum_total):.2f}%")
        md_lines.append(f"- Delta vs baseline: {float(baseline.get('delta_total_percent', 0.0)):+.2f}%")
        md_lines.append("")

    tracked_prefixes = report.get("tracked_prefixes", [])
    if isinstance(tracked_prefixes, list) and tracked_prefixes:
        md_lines.extend(
            [
                "## Tracked prefixes",
                "",
                "| Prefix | Coverage | Baseline | Delta | Status |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for item in tracked_prefixes:
            md_lines.append(
                f"| {item.get('prefix')} | {float(item.get('percent', 0.0)):.2f}% | "
                f"{float(item.get('baseline', 0.0)):.2f}% | {float(item.get('delta', 0.0)):+.2f}% | "
                f"{'FAIL' if item.get('status') == 'fail' else 'OK'} |"
            )
        md_lines.append("")

    watch_files = report.get("watch_files", [])
    if isinstance(watch_files, list) and watch_files:
        md_lines.extend(
            [
                "## Watch files",
                "",
                "| File | Coverage | Covered | Statements | Status |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for item in watch_files:
            percent = item.get("percent")
            percent_text = "-" if percent is None else f"{float(percent):.2f}%"
            md_lines.append(
                f"| {item.get('path')} | {percent_text} | {item.get('covered_lines', 0)} | "
                f"{item.get('num_statements', 0)} | {item.get('status')} |"
            )
        md_lines.append("")

    lowest = report.get("lowest_covered_files", [])
    if isinstance(lowest, list) and lowest:
        md_lines.extend(
            [
                "## Lowest-covered files",
                "",
                "| File | Coverage | Covered | Statements |",
                "|---|---:|---:|---:|",
            ]
        )
        for item in lowest:
            md_lines.append(
                f"| {item.get('path')} | {float(item.get('percent', 0.0)):.2f}% | {item.get('covered_lines', 0)} | "
                f"{item.get('num_statements', 0)} |"
            )
        md_lines.append("")

    regressions = baseline.get("regressions", [])
    if isinstance(regressions, list) and regressions:
        md_lines.extend(
            [
                "## Regressions",
                "",
                "| Kind | Target | Current | Baseline |",
                "|---|---|---:|---:|",
            ]
        )
        for item in regressions:
            md_lines.append(
                f"| {item.get('kind')} | {item.get('target')} | {float(item.get('current', 0.0)):.2f}% | "
                f"{float(item.get('baseline', 0.0)):.2f}% |"
            )
    else:
        md_lines.extend(["## Regressions", "", "No coverage regressions detected."])

    write_md(report_dir / _SUMMARY_MD_NAME, md_lines)


def _write_missing_capture_reports(*, report_dir: Path) -> None:
    payload = {
        "summary": {
            "status": "missing_capture",
            "total_percent": None,
            "covered_lines": None,
            "num_statements": None,
            "files": 0,
        },
        "baseline": {
            "minimum_total_percent": None,
            "delta_total_percent": None,
            "tracked_prefixes": {},
            "regressions": [],
        },
        "tracked_prefixes": [],
        "watch_files": [],
        "lowest_covered_files": [],
    }
    write_json(report_dir / _SUMMARY_JSON_NAME, payload)
    write_csv(
        report_dir / _SUMMARY_CSV_NAME,
        ["path", "percent", "covered_lines", "num_statements", "watched"],
        [],
    )
    write_md(
        report_dir / _SUMMARY_MD_NAME,
        [
            "# Coverage summary",
            "",
            "No fresh pytest coverage capture was found.",
            "",
            "Run one of:",
            "",
            "```bash",
            ".venv/bin/python -m buildpython --run-steps=2,18",
            ".venv/bin/python -m buildpython --profile debt",
            ".venv/bin/python -m buildpython --profile full",
            "```",
        ],
    )


def _run_pytest_under_coverage(*, root: Path, reason: str) -> RunResult:
    _clear_coverage_artifacts()
    result = run(
        [
            python_exe(),
            "-m",
            "coverage",
            "run",
            "--data-file",
            str(_coverage_data_file()),
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
        ],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
    if result.exit_code == 0:
        write_json(
            _capture_marker_file(),
            {
                "reason": reason,
                "data_file": str(_coverage_data_file()),
            },
        )
    return result


def _coverage_tool_available() -> bool:
    try:
        import coverage  # noqa: F401
    except ImportError:
        return False
    return True


def _has_fresh_pytest_coverage_data() -> bool:
    return _coverage_data_file().exists() and _capture_marker_file().exists()


def _coverage_data_file() -> Path:
    return buildlog_dir() / _DATA_FILE_NAME


def _capture_marker_file() -> Path:
    return buildlog_dir() / _CAPTURE_MARKER_NAME


def _clear_coverage_artifacts() -> None:
    for path in (
        _coverage_data_file(),
        _capture_marker_file(),
        buildlog_dir() / _RAW_JSON_NAME,
    ):
        try:
            path.unlink()
        except FileNotFoundError:
            continue


def _clear_coverage_report_artifacts() -> None:
    for path in (
        buildlog_dir() / _SUMMARY_JSON_NAME,
        buildlog_dir() / _SUMMARY_MD_NAME,
        buildlog_dir() / _SUMMARY_CSV_NAME,
    ):
        try:
            path.unlink()
        except FileNotFoundError:
            continue


def _load_coverage_baseline(root: Path) -> CoverageBaseline:
    config_path = root / _DEBT_BASELINE_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CoverageBaseline(minimum_total_percent=None, tracked_prefixes={}, watch_files=())

    section = payload.get("coverage", {})
    minimum_total_raw = section.get("minimum_total_percent")
    minimum_total = None
    if isinstance(minimum_total_raw, int | float):
        minimum_total = float(minimum_total_raw)

    tracked_prefixes_raw = section.get("tracked_prefixes", {})
    tracked_prefixes = {
        str(prefix): float(value)
        for prefix, value in tracked_prefixes_raw.items()
        if isinstance(prefix, str) and isinstance(value, int | float)
    }

    watch_files = tuple(str(path) for path in section.get("watch_files", []) if isinstance(path, str))
    return CoverageBaseline(
        minimum_total_percent=minimum_total,
        tracked_prefixes=tracked_prefixes,
        watch_files=watch_files,
    )


def _load_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _normalize_files(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_files = payload.get("files", {})
    if not isinstance(raw_files, dict):
        return {}

    files: dict[str, dict[str, Any]] = {}
    for rel_path, file_payload in raw_files.items():
        if not isinstance(rel_path, str) or not isinstance(file_payload, dict):
            continue
        summary = file_payload.get("summary", {})
        if not isinstance(summary, dict):
            continue
        covered = int(summary.get("covered_lines", 0) or 0)
        statements = int(summary.get("num_statements", 0) or 0)
        files[rel_path] = {
            "covered_lines": covered,
            "num_statements": statements,
            "percent": _percent_from_counts(covered=covered, statements=statements),
        }
    return files


def _extract_totals(payload: dict[str, Any]) -> dict[str, int]:
    totals = payload.get("totals", {})
    if not isinstance(totals, dict):
        return {"covered_lines": 0, "num_statements": 0}
    return {
        "covered_lines": int(totals.get("covered_lines", 0) or 0),
        "num_statements": int(totals.get("num_statements", 0) or 0),
    }


def _aggregate_prefix(files: dict[str, dict[str, Any]], prefix: str) -> dict[str, int]:
    covered = 0
    statements = 0
    for rel_path, summary in files.items():
        if rel_path.startswith(prefix):
            covered += int(summary.get("covered_lines", 0))
            statements += int(summary.get("num_statements", 0))
    return {"covered_lines": covered, "num_statements": statements}


def _percent_from_counts(*, covered: int, statements: int) -> float:
    if statements <= 0:
        return 0.0
    return round((covered / statements) * 100.0, 2)
