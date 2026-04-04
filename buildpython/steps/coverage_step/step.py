from __future__ import annotations

from ...utils.paths import buildlog_dir, repo_root
from ...utils.subproc import RunResult, python_exe, run
from .constants import _RAW_JSON_NAME
from .models import CoverageBaseline
from .payload import build_coverage_report, _load_coverage_baseline, _load_json_file
from .reporting import _build_stdout, _write_coverage_reports, _write_missing_capture_reports
from .runtime import (
    _clear_coverage_report_artifacts,
    _coverage_data_file,
    _coverage_tool_available,
    _has_fresh_pytest_coverage_data,
    pytest_runner_with_optional_coverage as _pytest_runner_with_optional_coverage,
)


def pytest_runner_with_optional_coverage() -> RunResult:
    return _pytest_runner_with_optional_coverage(root=repo_root())


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

    stdout_lines = _build_stdout(report, reports_path=buildlog_dir())
    regressions = report.get("baseline", {}).get("regressions", [])
    exit_code = 1 if regressions else 0
    return RunResult(
        command_str="(internal) coverage summary",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )
