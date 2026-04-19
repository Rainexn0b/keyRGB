from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import buildpython.steps.code_hygiene.step as step_code_hygiene
import buildpython.steps.code_hygiene.baseline as step_code_hygiene_baseline
import buildpython.steps.code_hygiene.text_scanners as text_scanners
import buildpython.steps.file_size_analysis._ast_scan_helpers as file_size_ast_scan_helpers

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
from buildpython.steps.code_hygiene.baseline import _path_budget_regressions
from buildpython.steps.code_hygiene.models import HygieneBaseline, HygieneIssue
from buildpython.steps.exception_transparency.models import ExceptionTransparencyAnnotationInventory
from buildpython.steps.exception_transparency.reporting import build_stdout, write_reports
from buildpython.steps.exception_transparency.scanner import collect_annotation_inventory, collect_findings
from buildpython.steps.coverage_step.step import CoverageBaseline, build_coverage_report
from buildpython.steps.exception_transparency.step import _scan_python_source


def test_exception_transparency_scan_suppresses_valid_quality_exception_waivers() -> None:
    findings = _scan_python_source(
        """
def example():
    try:
        run_one()
    # @quality-exception exception-transparency: optional runtime boundary for startup fallback
    except Exception:
        pass

    try:
        run_two()
    except Exception:  # @quality-exception exception-transparency: shutdown cleanup boundary
        pass
""".strip(),
        rel_path="src/example.py",
    )

    assert findings == []


def test_exception_transparency_scan_ignores_indented_preceding_quality_exception_comment() -> None:
    findings = _scan_python_source(
        """
def example():
    try:
        run_one()
        # @quality-exception exception-transparency: try-body comment should not waive the handler
    except Exception:
        pass
""".strip(),
        rel_path="src/example.py",
    )

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1

    assert counts["broad_except_total"] == 1
    assert counts["broad_except_unlogged"] == 1


def test_exception_transparency_scan_ignores_other_step_quality_exception_tags() -> None:
    findings = _scan_python_source(
        """
def example():
    try:
        run_one()
    except Exception:  # @quality-exception coverage: tracked by another step
        pass
""".strip(),
        rel_path="src/example.py",
    )

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1

    assert counts["broad_except_total"] == 1
    assert counts["broad_except_unlogged"] == 1


def test_exception_transparency_scan_requires_quality_exception_explanation() -> None:
    findings = _scan_python_source(
        """
def example():
    try:
        run_one()
    except Exception:  # @quality-exception exception-transparency
        pass
""".strip(),
        rel_path="src/example.py",
    )

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1

    assert counts["broad_except_total"] == 1
    assert counts["broad_except_unlogged"] == 1


def test_exception_transparency_scan_classifies_broad_handlers_without_waivers() -> None:
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


def test_exception_transparency_scan_skips_unparseable_source() -> None:
    findings = _scan_python_source(
        """
def broken(:
    pass
""".strip(),
        rel_path="src/example.py",
    )

    assert findings == []


def test_exception_transparency_collect_findings_skips_unreadable_files(tmp_path, monkeypatch) -> None:
    readable = tmp_path / "src" / "ok.py"
    unreadable = tmp_path / "buildpython" / "blocked.py"
    readable.parent.mkdir(parents=True)
    unreadable.parent.mkdir(parents=True)
    readable.write_text(
        """
def example():
    try:
        run_one()
    except Exception:
        pass
""".strip(),
        encoding="utf-8",
    )
    unreadable.write_text("def blocked():\n    return None\n", encoding="utf-8")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs) -> str:
        if self == unreadable:
            raise OSError("permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert {finding.category for finding in collect_findings(tmp_path)} == {
        "broad_except_total",
        "broad_except_unlogged",
    }


def test_exception_transparency_collect_annotation_inventory_groups_valid_tags_by_subtree(tmp_path) -> None:
    tray_file = tmp_path / "src" / "tray" / "runtime.py"
    helper_file = tmp_path / "buildpython" / "core" / "helpers.py"
    tray_file.parent.mkdir(parents=True)
    helper_file.parent.mkdir(parents=True)
    tray_file.write_text(
        """
def run_tray():
    # @quality-exception exception-transparency: tray startup boundary
    try:
        launch()
    except RuntimeError:  # @quality-exception exception-transparency: tray runtime boundary
        return None
""".strip(),
        encoding="utf-8",
    )
    helper_file.write_text(
        """
def run_helper():
    # @quality-exception exception-transparency: build helper boundary
    return True

def ignored_helper():
    # @quality-exception exception-transparency
    return False
""".strip(),
        encoding="utf-8",
    )

    inventory = collect_annotation_inventory(tmp_path)

    assert inventory.total == 3
    assert inventory.by_subtree == (("src/tray", 2), ("buildpython/core", 1))


def test_exception_transparency_reports_include_annotation_inventory(tmp_path) -> None:
    inventory = ExceptionTransparencyAnnotationInventory(
        total=3,
        by_subtree=(("src/tray", 2), ("src/core", 1)),
    )

    stdout_lines = build_stdout([], Counter(), 0, inventory)
    write_reports(tmp_path, [], Counter(), 0, inventory)

    report_dir = tmp_path / "buildlog" / "keyrgb"
    payload = json.loads((report_dir / "exception-transparency.json").read_text(encoding="utf-8"))
    report_md = (report_dir / "exception-transparency.md").read_text(encoding="utf-8")

    assert any("Valid @quality-exception exception-transparency annotations: 3" in line for line in stdout_lines)
    assert payload["annotation_inventory"] == {
        "total": 3,
        "by_subtree": [
            {"subtree": "src/tray", "count": 2},
            {"subtree": "src/core", "count": 1},
        ],
    }
    assert "## Runtime-Boundary Annotation Inventory" in report_md
    assert "| src/tray | 2 |" in report_md


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


def test_load_hygiene_baseline_returns_empty_on_invalid_json(tmp_path) -> None:
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text("{not valid json", encoding="utf-8")

    baseline = step_code_hygiene_baseline._load_hygiene_baseline(tmp_path)

    assert baseline == HygieneBaseline(counts={}, gated_categories=set(), path_budgets={})


def test_code_hygiene_runner_uses_cleanup_hotspot_threshold_from_baseline(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text(
        json.dumps(
            {
                "code_hygiene": {
                    "counts": {
                        "cleanup_hotspot": 94,
                        "silent_broad_except": 0,
                    },
                    "gated_categories": ["cleanup_hotspot", "silent_broad_except"],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    issues = [
        HygieneIssue(
            category="cleanup_hotspot",
            path="src/example.py",
            line=line,
            message="msg",
            snippet="# TODO",
        )
        for line in range(1, 96)
    ]

    monkeypatch.setattr(step_code_hygiene, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_code_hygiene, "_collect_all_issues", lambda _root: issues)

    result = step_code_hygiene.code_hygiene_runner()
    report = json.loads((tmp_path / "buildlog" / "keyrgb" / "code-hygiene.json").read_text(encoding="utf-8"))

    assert result.exit_code == 1
    assert report["thresholds"]["cleanup_hotspot"] == 94
    assert report["active_counts"]["cleanup_hotspot"] == 95


def test_code_hygiene_runner_keeps_non_cleanup_thresholds_unchanged(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text(
        json.dumps(
            {
                "code_hygiene": {
                    "counts": {
                        "cleanup_hotspot": 94,
                        "silent_broad_except": 0,
                    },
                    "gated_categories": ["cleanup_hotspot", "silent_broad_except"],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    issues = [
        HygieneIssue(
            category="silent_broad_except",
            path="src/example.py",
            line=1,
            message="msg",
            snippet="except Exception:",
        )
    ]

    monkeypatch.setattr(step_code_hygiene, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_code_hygiene, "_collect_all_issues", lambda _root: issues)

    result = step_code_hygiene.code_hygiene_runner()
    report = json.loads((tmp_path / "buildlog" / "keyrgb" / "code-hygiene.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert report["thresholds"]["cleanup_hotspot"] == 94
    assert report["thresholds"]["silent_broad_except"] == 4


def test_hygiene_detectors_ignore_missing_or_unparseable_sources(tmp_path) -> None:
    root = tmp_path
    missing_file = root / "src" / "missing.py"
    broken_file = root / "src" / "tray" / "ui" / "broken.py"
    broken_file.parent.mkdir(parents=True)
    broken_file.write_text("def broken(:\n    pass\n", encoding="utf-8")

    assert step_code_hygiene._detect_cleanup_hotspots(missing_file, root) == []
    assert step_code_hygiene._detect_runtime_copy_hotspots(broken_file, root) == []
    assert step_code_hygiene._detect_broad_exception_patterns(broken_file, root) == []


def test_text_scanners_match_representative_cleanup_and_defensive_patterns(tmp_path) -> None:
    root = tmp_path
    target = root / "buildpython" / "example.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        """
value = int(int(raw))
flag = bool(bool(raw_flag))
ratio = float(float(raw_ratio))
name = str(str(raw_name))
fallback = int(getattr(obj, \"count\") or 0)
return int(int(result))
# TODO: refactor me
# FIXME: tighten this later
# HACK: compatibility shim
# LEGACY: keep while migrating
# FACADE: remove after split
legacy_alias = thing
facade_alias = thing
migrate_legacy(profile)
compat_layer = True
""".strip(),
        encoding="utf-8",
    )

    defensive_issues = text_scanners._detect_defensive_conversions(target, root)
    cleanup_issues = text_scanners._detect_cleanup_hotspots(target, root)

    assert [issue.line for issue in defensive_issues] == [1, 2, 3, 4, 5, 6, 6]
    assert [issue.message for issue in defensive_issues] == [
        "nested int(int(...))",
        "nested bool(bool(...))",
        "nested float(float(...))",
        "nested str(str(...))",
        "int(getattr(...) or 0) - consider default param",
        "nested int(int(...))",
        "return int(int(...))",
    ]
    assert [issue.line for issue in cleanup_issues] == [7, 8, 9, 10, 11, 12, 13, 14, 15]
    assert all(
        issue.message == "Cleanup/facade/legacy marker found: consider refactor or migration plan"
        for issue in cleanup_issues
    )


def test_text_scanners_do_not_self_flag_cleanup_or_defensive_patterns() -> None:
    scanner_path = Path(text_scanners.__file__).resolve()
    ast_helper_path = Path(file_size_ast_scan_helpers.__file__).resolve()
    root = scanner_path.parents[3]

    assert text_scanners._detect_defensive_conversions(scanner_path, root) == []
    assert text_scanners._detect_cleanup_hotspots(scanner_path, root) == []
    assert text_scanners._detect_cleanup_hotspots(ast_helper_path, root) == []


def test_any_type_hint_scanner_covers_all_src_including_gui_paths(tmp_path) -> None:
    root = tmp_path
    gui_target = root / "src" / "gui" / "perkey" / "editor.py"
    helper_target = root / "buildpython" / "helper.py"
    gui_target.parent.mkdir(parents=True)
    helper_target.parent.mkdir(parents=True)

    gui_target.write_text(
        "from typing import Any\n\n"
        "def initialize_editor(editor: Any) -> Any:\n"
        "    return editor\n",
        encoding="utf-8",
    )
    helper_target.write_text(
        "from typing import Any\n\n"
        "def helper(value: Any) -> Any:\n"
        "    return value\n",
        encoding="utf-8",
    )

    issues = text_scanners._detect_any_type_hints(gui_target, root)

    assert [
        (issue.path, issue.line, issue.message)
        for issue in issues
    ] == [
        (
            "src/gui/perkey/editor.py",
            3,
            "Parameter typed as Any - consider Protocol or concrete type",
        ),
        (
            "src/gui/perkey/editor.py",
            3,
            "Return typed as Any - consider Protocol or concrete type",
        ),
    ]
    assert text_scanners._detect_any_type_hints(helper_target, root) == []


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
                        {"subtree": "src/tray", "count": 63},
                        {"subtree": "src/core", "count": 36},
                        {"subtree": "src/gui", "count": 3},
                    ],
                },
                "top_files_by_category": {"broad_except_unlogged": [{"path": "src/core/config/config.py", "count": 3}]},
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
    assert "Top annotation subtrees: src/tray (63), src/core (36), src/gui (3)" in debt_index_md


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
                        {"subtree": "src/tray", "count": 63},
                        {"subtree": "src/core", "count": 36},
                        {"subtree": "src/gui", "count": 3},
                    ],
                },
                "top_files_by_category": {
                    "broad_except_unlogged": [{"path": "src/core/config/config.py", "count": 3}],
                    "broad_except_total": [{"path": "src/core/config/config.py", "count": 4}],
                },
            }
        ),
        encoding="utf-8",
    )

    lines = build_terminal_transparency_highlight(buildlog_dir)

    assert any("total 6 (205)" in line for line in lines)
    assert any("unlogged 4" in line for line in lines)
    assert any("annotated 102" in line for line in lines)
    assert any("Top unlogged" in line and "src/core/config/config.py" in line for line in lines)
    assert any("Top annotated" in line and "src/tray" in line for line in lines)


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
                        {"subtree": "src/tray", "count": 63},
                        {"subtree": "src/core", "count": 36},
                        {"subtree": "src/gui", "count": 3},
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
    assert "Top annotation subtrees: src/tray (63), src/core (36), src/gui (3)" in build_summary_md


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
    assert "File buckets: monitor=1, refactor=1, severe=1" in build_summary_md
    assert "Test-scope hits: 1" in build_summary_md
    assert "Largest file: tests/test_big.py (620 lines, SEVERE)" in build_summary_md

    assert "## LOC check" in debt_index_md
    assert "File buckets: monitor=1, refactor=1, severe=1" in debt_index_md
    assert "Default-scope hits: 2" in debt_index_md
    assert "Test-scope hits: 1" in debt_index_md

    assert any("tests 1" in line for line in terminal_lines)


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

    assert any("Build Results" in line for line in lines)
    assert any("PASS" in line for line in lines)
    assert any("100/100" in line for line in lines)
    assert any("59.49%" in line and "73.28%" in line for line in lines)
