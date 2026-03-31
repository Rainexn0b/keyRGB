from __future__ import annotations

import json

from buildpython.core.debt_index import build_debt_index, write_debt_index
from buildpython.core.summary import (
    BuildSummary,
    build_terminal_build_overview,
    build_terminal_coverage_highlight,
    build_terminal_debt_snapshot,
    write_summary,
)
from buildpython.steps.step_code_hygiene import HygieneBaseline, HygieneIssue, _path_budget_regressions
from buildpython.steps.step_coverage import CoverageBaseline, build_coverage_report
from buildpython.steps.step_exception_transparency import _scan_python_source


def test_exception_transparency_scan_classifies_broad_handlers() -> None:
    findings = _scan_python_source(
        """
from src.core.utils.logging_utils import log_throttled

def example(logger):
    try:
        run_one()
    except Exception:
        pass

    try:
        run_two()
    except Exception:
        logger.warning('warn only')

    try:
        run_three()
    except Exception as exc:
        logger.exception('boom: %s', exc)

    try:
        run_throttled()
    except Exception as exc:
        log_throttled(logger, 'demo', interval_s=60, level=40, msg='throttled', exc=exc)

    try:
        run_four()
    except BaseException:
        return None
""".strip(),
        rel_path="src/example.py",
    )

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1

    assert counts["broad_except_total"] == 5
    assert counts["broad_except_unlogged"] == 2
    assert counts["broad_except_logged_no_traceback"] == 1
    assert counts["broad_except_traceback_logged"] == 2
    assert counts["baseexception_catch"] == 1
    assert counts.get("naked_except", 0) == 0


def test_path_budget_regressions_flag_specific_hotspots() -> None:
    issues = [
        HygieneIssue(
            category="silent_broad_except",
            path="src/tray/app/application.py",
            line=1,
            message="msg",
            snippet="except Exception:",
        ),
        HygieneIssue(
            category="silent_broad_except",
            path="src/tray/app/application.py",
            line=2,
            message="msg",
            snippet="except Exception:",
        ),
        HygieneIssue(
            category="fallback_broad_except",
            path="src/core/config/config.py",
            line=3,
            message="msg",
            snippet="except Exception:",
        ),
    ]
    baseline = HygieneBaseline(
        counts={},
        gated_categories=set(),
        path_budgets={
            "silent_broad_except": {"src/tray/app/application.py": 1},
            "fallback_broad_except": {"src/core/config/config.py": 2},
        },
    )

    regressions = _path_budget_regressions(issues, baseline)

    assert regressions == [("silent_broad_except", "src/tray/app/application.py", 2, 1)]


def test_build_coverage_report_tracks_prefixes_and_watch_files() -> None:
    payload = {
        "files": {
            "src/core/config/config.py": {
                "summary": {
                    "covered_lines": 50,
                    "num_statements": 100,
                }
            },
            "src/tray/app/application.py": {
                "summary": {
                    "covered_lines": 20,
                    "num_statements": 40,
                }
            },
            "src/core/backends/sysfs/device.py": {
                "summary": {
                    "covered_lines": 0,
                    "num_statements": 30,
                }
            },
        },
        "totals": {
            "covered_lines": 70,
            "num_statements": 170,
        },
    }
    baseline = CoverageBaseline(
        minimum_total_percent=40.0,
        tracked_prefixes={
            "src/core/": 45.0,
            "src/tray/": 40.0,
        },
        watch_files=(
            "src/core/backends/sysfs/device.py",
            "src/core/config/config.py",
        ),
    )

    report = build_coverage_report(payload, baseline)

    assert report["summary"]["total_percent"] == 41.18
    tracked = {item["prefix"]: item for item in report["tracked_prefixes"]}
    assert tracked["src/core/"]["percent"] == 38.46
    assert tracked["src/core/"]["status"] == "fail"
    assert tracked["src/tray/"]["percent"] == 50.0
    watch = {item["path"]: item for item in report["watch_files"]}
    assert watch["src/core/backends/sysfs/device.py"]["percent"] == 0.0
    assert len(report["baseline"]["regressions"]) == 1


def test_write_debt_index_aggregates_reports(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "code-hygiene.json").write_text(
        json.dumps(
            {
                "counts": {"silent_broad_except": 3},
                "baseline": {
                    "regressions": [],
                    "path_budget_regressions": [
                        {
                            "category": "silent_broad_except",
                            "path": "src/tray/app/application.py",
                            "current": 3,
                            "baseline": 2,
                        }
                    ],
                },
                "top_files_by_category": {},
            }
        ),
        encoding="utf-8",
    )
    (buildlog_dir / "exception-transparency.json").write_text(
        json.dumps(
            {
                "counts": {
                    "broad_except_total": 5,
                    "broad_except_unlogged": 4,
                    "broad_except_logged_no_traceback": 1,
                    "broad_except_traceback_logged": 0,
                    "naked_except": 0,
                    "baseexception_catch": 0,
                },
                "baseline": {"regressions": []},
                "top_files_by_category": {
                    "broad_except_unlogged": [{"path": "src/core/config/config.py", "count": 3}]
                },
            }
        ),
        encoding="utf-8",
    )
    (buildlog_dir / "coverage-summary.json").write_text(
        json.dumps(
            {
                "summary": {"total_percent": 12.5},
                "baseline": {"regressions": []},
                "tracked_prefixes": [],
                "watch_files": [],
            }
        ),
        encoding="utf-8",
    )
    (buildlog_dir / "architecture-validation.json").write_text(
        json.dumps({"summary": {"findings": 0, "errors": 0, "warnings": 0}}),
        encoding="utf-8",
    )

    payload = build_debt_index(buildlog_dir)
    write_debt_index(buildlog_dir)

    assert payload["summary"]["report_count"] == 4
    assert "coverage" in payload["sections"]
    assert "exception_transparency" in payload["sections"]
    assert (buildlog_dir / "debt-index.json").exists()
    assert (buildlog_dir / "debt-index.md").exists()


def test_terminal_debt_snapshot_includes_exception_transparency(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "exception-transparency.json").write_text(
        json.dumps(
            {
                "counts": {
                    "broad_except_total": 6,
                    "broad_except_unlogged": 4,
                    "broad_except_logged_no_traceback": 1,
                    "broad_except_traceback_logged": 1,
                    "naked_except": 0,
                    "baseexception_catch": 0,
                },
                "baseline": {
                    "counts": {
                        "broad_except_total": 6,
                        "broad_except_unlogged": 4,
                        "broad_except_logged_no_traceback": 1,
                        "broad_except_traceback_logged": 1,
                        "naked_except": 0,
                        "baseexception_catch": 0,
                    },
                    "regressions": [],
                },
                "top_files_by_category": {
                    "broad_except_unlogged": [{"path": "src/core/config/config.py", "count": 3}],
                    "broad_except_total": [{"path": "src/core/config/config.py", "count": 4}],
                },
            }
        ),
        encoding="utf-8",
    )

    lines = build_terminal_debt_snapshot(buildlog_dir, include_coverage=False)

    assert any("Exception transparency:" in line for line in lines)
    assert any("Top unlogged broad catch: src/core/config/config.py (3)" in line for line in lines)


def test_terminal_debt_snapshot_marks_missing_coverage_capture(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "coverage-summary.json").write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )

    lines = build_terminal_debt_snapshot(buildlog_dir)

    assert any("Coverage: missing capture" in line for line in lines)
    assert not any("Coverage: total=0.00%" in line for line in lines)


def test_write_summary_and_debt_index_render_missing_capture_state(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "coverage-summary.json").write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )

    write_summary(
        buildlog_dir,
        BuildSummary(
            passed=False,
            health_score=0,
            total_duration_s=0.1,
            steps=[],
        ),
    )
    write_debt_index(buildlog_dir)

    build_summary_md = (buildlog_dir / "build-summary.md").read_text(encoding="utf-8")
    debt_index_md = (buildlog_dir / "debt-index.md").read_text(encoding="utf-8")

    assert "Status: waiting for pytest coverage capture" in build_summary_md
    assert "Total coverage: 0.0%" not in build_summary_md
    assert "Status: waiting for pytest coverage capture" in debt_index_md
    assert "Total coverage: 0.0%" not in debt_index_md


def test_terminal_coverage_highlight_summarizes_total_and_prefixes(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "coverage-summary.json").write_text(
        json.dumps(
            {
                "summary": {"total_percent": 59.49},
                "baseline": {"regressions": []},
                "tracked_prefixes": [
                    {"prefix": "src/core/", "percent": 73.28},
                    {"prefix": "src/tray/", "percent": 73.85},
                    {"prefix": "src/gui/", "percent": 27.50},
                ],
                "watch_files": [],
            }
        ),
        encoding="utf-8",
    )

    line = build_terminal_coverage_highlight(buildlog_dir)

    assert line == "Coverage: 59.49% total | core 73.28% | tray 73.85% | gui 27.50%"


def test_terminal_build_overview_includes_status_health_and_coverage(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "coverage-summary.json").write_text(
        json.dumps(
            {
                "summary": {"total_percent": 59.49},
                "baseline": {"regressions": []},
                "tracked_prefixes": [
                    {"prefix": "src/core/", "percent": 73.28},
                    {"prefix": "src/tray/", "percent": 73.85},
                    {"prefix": "src/gui/", "percent": 27.50},
                ],
                "watch_files": [],
            }
        ),
        encoding="utf-8",
    )

    lines = build_terminal_build_overview(
        buildlog_dir,
        BuildSummary(
            passed=True,
            health_score=100,
            total_duration_s=3.4,
            steps=[],
        ),
    )

    assert lines[0] == "Build summary:"
    assert "Status: PASS" in lines[1]
    assert "Health: 100/100" in lines[4]
    assert lines[5] == "  Coverage: 59.49% total | core 73.28% | tray 73.85% | gui 27.50%"