from __future__ import annotations

import json

from buildpython.core.debt_index import build_debt_index, write_debt_index
from buildpython.core.summary import (
    BuildSummary,
    build_terminal_build_overview,
    build_terminal_coverage_highlight,
    write_summary,
)
from buildpython.core.summary_support.debt_terminal import (
    build_terminal_loc_check_highlight,
    build_terminal_transparency_highlight,
)
from buildpython.steps.coverage_step.step import CoverageBaseline, build_coverage_report


def test_build_coverage_report_tracks_prefixes_and_watch_files() -> None:
    payload = {
        "files": {
            "keyrgb/core/config/config.py": {
                "summary": {
                    "covered_lines": 50,
                    "num_statements": 100,
                }
            },
            "keyrgb/tray/app/application.py": {
                "summary": {
                    "covered_lines": 20,
                    "num_statements": 40,
                }
            },
            "keyrgb/core/backends/sysfs/device.py": {
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
            "keyrgb/core/": 45.0,
            "keyrgb/tray/": 40.0,
        },
        watch_files=(
            "keyrgb/core/backends/sysfs/device.py",
            "keyrgb/core/config/config.py",
        ),
    )

    report = build_coverage_report(payload, baseline)

    assert report["summary"]["total_percent"] == 41.18
    tracked = {item["prefix"]: item for item in report["tracked_prefixes"]}
    assert tracked["keyrgb/core/"]["percent"] == 38.46
    assert tracked["keyrgb/core/"]["status"] == "fail"
    assert tracked["keyrgb/tray/"]["percent"] == 50.0
    watch = {item["path"]: item for item in report["watch_files"]}
    assert watch["keyrgb/core/backends/sysfs/device.py"]["percent"] == 0.0
    assert len(report["baseline"]["regressions"]) == 1


def test_build_coverage_report_fails_missing_and_undercovered_watch_files() -> None:
    payload = {
        "files": {
            "keyrgb/core/present.py": {
                "summary": {
                    "covered_lines": 1,
                    "num_statements": 10,
                }
            },
        },
        "totals": {"covered_lines": 1, "num_statements": 10},
    }
    baseline = CoverageBaseline(
        minimum_total_percent=None,
        tracked_prefixes={},
        watch_files=("keyrgb/core/present.py", "keyrgb/core/missing.py"),
        minimum_watch_file_percent=20.0,
    )

    report = build_coverage_report(payload, baseline)

    watch = {item["path"]: item for item in report["watch_files"]}
    assert watch["keyrgb/core/present.py"]["status"] == "fail"
    assert watch["keyrgb/core/missing.py"]["status"] == "missing"
    assert {(item["kind"], item["target"]) for item in report["baseline"]["regressions"]} == {
        ("watch_file", "keyrgb/core/present.py"),
        ("watch_missing", "keyrgb/core/missing.py"),
    }


def test_write_debt_index_aggregates_reports(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "code-hygiene.json").write_text(
        json.dumps(
            {
                "active_counts": {"silent_broad_except": 3},
                "suppressed_counts": {"silent_broad_except": 5},
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
                "waived_total": 205,
                "annotation_inventory": {
                    "total": 102,
                    "by_subtree": [
                        {"subtree": "keyrgb/tray", "count": 63},
                        {"subtree": "keyrgb/core", "count": 36},
                        {"subtree": "keyrgb/gui", "count": 3},
                    ],
                },
                "top_files_by_category": {
                    "broad_except_unlogged": [{"path": "keyrgb/core/config/config.py", "count": 3}]
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
    assert payload["sections"]["exception_transparency"]["annotation_inventory"]["total"] == 102
    assert (buildlog_dir / "debt-index.json").exists()
    assert (buildlog_dir / "debt-index.md").exists()

    debt_index_md = (buildlog_dir / "debt-index.md").read_text(encoding="utf-8")

    assert "Runtime-boundary annotations: 102" in debt_index_md
    assert "Top annotation subtrees: keyrgb/tray (63), keyrgb/core (36), keyrgb/gui (3)" in debt_index_md


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
                "waived_total": 205,
                "annotation_inventory": {
                    "total": 102,
                    "by_subtree": [
                        {"subtree": "keyrgb/tray", "count": 63},
                        {"subtree": "keyrgb/core", "count": 36},
                        {"subtree": "keyrgb/gui", "count": 3},
                    ],
                },
                "top_files_by_category": {
                    "broad_except_unlogged": [{"path": "keyrgb/core/config/config.py", "count": 3}],
                    "broad_except_total": [{"path": "keyrgb/core/config/config.py", "count": 4}],
                },
            }
        ),
        encoding="utf-8",
    )

    lines = build_terminal_transparency_highlight(buildlog_dir)

    assert any("total 6 (205)" in line for line in lines)
    assert any("unlogged 4" in line for line in lines)
    assert any("annotated 102" in line for line in lines)
    assert any("Top unlogged" in line and "keyrgb/core/config/config.py" in line for line in lines)
    assert any("Top annotated" in line and "keyrgb/tray" in line for line in lines)


def test_write_summary_includes_exception_transparency_annotation_inventory(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "exception-transparency.json").write_text(
        json.dumps(
            {
                "counts": {
                    "broad_except_total": 0,
                    "broad_except_unlogged": 0,
                    "broad_except_logged_no_traceback": 0,
                    "broad_except_traceback_logged": 0,
                    "naked_except": 0,
                    "baseexception_catch": 0,
                },
                "waived_total": 0,
                "annotation_inventory": {
                    "total": 102,
                    "by_subtree": [
                        {"subtree": "keyrgb/tray", "count": 63},
                        {"subtree": "keyrgb/core", "count": 36},
                        {"subtree": "keyrgb/gui", "count": 3},
                    ],
                },
                "top_files_by_category": {},
            }
        ),
        encoding="utf-8",
    )

    write_summary(
        buildlog_dir,
        BuildSummary(
            passed=True,
            health_score=100,
            total_duration_s=0.1,
            steps=[],
        ),
    )

    build_summary_md = (buildlog_dir / "build-summary.md").read_text(encoding="utf-8")

    assert "Runtime-boundary annotations: 102" in build_summary_md
    assert "Top annotation subtrees: keyrgb/tray (63), keyrgb/core (36), keyrgb/gui (3)" in build_summary_md


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

    coverage_line = build_terminal_coverage_highlight(buildlog_dir)
    lines = [coverage_line] if coverage_line is not None else []

    assert any("waiting for pytest coverage capture" in line for line in lines)
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


def test_write_summary_and_debt_index_include_loc_check_snapshot(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "loc-check.json").write_text(
        json.dumps(
            {
                "count": 3,
                "counts": {"monitor": 1, "refactor": 1, "critical": 0, "severe": 1, "total": 3},
                "counts_by_scope": {
                    "default": {"monitor": 1, "refactor": 1, "critical": 0, "severe": 0, "total": 2},
                    "tests": {"monitor": 0, "refactor": 0, "critical": 0, "severe": 1, "total": 1},
                },
                "files": [{"path": "tests/test_big.py", "lines": 620, "bucket": "SEVERE", "scope": "tests"}],
            }
        ),
        encoding="utf-8",
    )

    write_summary(
        buildlog_dir,
        BuildSummary(
            passed=True,
            health_score=100,
            total_duration_s=0.1,
            steps=[],
        ),
    )
    write_debt_index(buildlog_dir)

    build_summary_md = (buildlog_dir / "build-summary.md").read_text(encoding="utf-8")
    debt_index_md = (buildlog_dir / "debt-index.md").read_text(encoding="utf-8")
    terminal_lines = build_terminal_loc_check_highlight(buildlog_dir)

    assert "### LOC Check" in build_summary_md
    assert "File buckets: monitor=1, refactor=1, severe=1 (default 0, tests 1)" in build_summary_md
    assert "Test-scope hits: 1" in build_summary_md
    assert "Largest file: tests/test_big.py (620 lines, SEVERE)" in build_summary_md

    assert "## LOC check" in debt_index_md
    assert "File buckets: monitor=1, refactor=1, severe=1 (default 0, tests 1)" in debt_index_md
    assert "Default-scope hits: 2" in debt_index_md
    assert "Test-scope hits: 1" in debt_index_md

    assert any("severe 1 (0 default, 1 tests)" in line for line in terminal_lines)


def test_terminal_coverage_highlight_summarizes_total_and_prefixes(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "coverage-summary.json").write_text(
        json.dumps(
            {
                "summary": {"total_percent": 59.49},
                "baseline": {"regressions": []},
                "tracked_prefixes": [
                    {"prefix": "keyrgb/core/", "percent": 73.28},
                    {"prefix": "keyrgb/tray/", "percent": 73.85},
                    {"prefix": "keyrgb/gui/", "percent": 27.50},
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
                    {"prefix": "keyrgb/core/", "percent": 73.28},
                    {"prefix": "keyrgb/tray/", "percent": 73.85},
                    {"prefix": "keyrgb/gui/", "percent": 27.50},
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

    assert any("Build Results" in line for line in lines)
    assert any("PASS" in line for line in lines)
    assert any("100/100" in line for line in lines)
    assert any("59.49%" in line and "73.28%" in line for line in lines)
