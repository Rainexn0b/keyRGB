from __future__ import annotations

import json
from pathlib import Path

from buildpython.steps.coverage_step.models import CoverageBaseline
from buildpython.steps.coverage_step.payload import _load_coverage_baseline, build_coverage_report
from buildpython.steps.coverage_step.reporting import _build_stdout, _write_coverage_reports

_HELPER = "system/bin/keyrgb-power-helper"


def _payload_with_helper(*, covered: int, statements: int) -> dict:
    return {
        "files": {
            _HELPER: {"summary": {"covered_lines": covered, "num_statements": statements}},
            "keyrgb/core/example.py": {"summary": {"covered_lines": 10, "num_statements": 10}},
        },
        "totals": {"covered_lines": covered + 10, "num_statements": statements + 10},
    }


def _baseline_with_helper(*, threshold: float) -> CoverageBaseline:
    return CoverageBaseline(
        minimum_total_percent=None,
        tracked_prefixes={},
        watch_files=(),
        per_file_minimums={_HELPER: threshold},
    )


def test_per_file_minimum_passes_when_helper_above_threshold() -> None:
    report = build_coverage_report(
        _payload_with_helper(covered=40, statements=100), _baseline_with_helper(threshold=30.0)
    )

    rows = {item["path"]: item for item in report["per_file_minimums"]}
    assert rows[_HELPER]["percent"] == 40.0
    assert rows[_HELPER]["status"] == "ok"
    assert report["baseline"]["regressions"] == []
    assert report["baseline"]["per_file_minimums"] == {_HELPER: 30.0}


def test_per_file_minimum_regresses_when_helper_below_threshold() -> None:
    report = build_coverage_report(
        _payload_with_helper(covered=10, statements=100), _baseline_with_helper(threshold=30.0)
    )

    rows = {item["path"]: item for item in report["per_file_minimums"]}
    assert rows[_HELPER]["status"] == "fail"
    assert {(item["kind"], item["target"]) for item in report["baseline"]["regressions"]} == {("per_file", _HELPER)}


def test_per_file_minimum_regresses_when_helper_missing_from_payload() -> None:
    payload = {
        "files": {"keyrgb/core/example.py": {"summary": {"covered_lines": 10, "num_statements": 10}}},
        "totals": {"covered_lines": 10, "num_statements": 10},
    }

    report = build_coverage_report(payload, _baseline_with_helper(threshold=30.0))

    rows = {item["path"]: item for item in report["per_file_minimums"]}
    assert rows[_HELPER]["status"] == "missing"
    assert {(item["kind"], item["target"]) for item in report["baseline"]["regressions"]} == {
        ("per_file_missing", _HELPER)
    }


def test_per_file_minimums_default_to_empty_for_legacy_baselines() -> None:
    baseline = CoverageBaseline(minimum_total_percent=None, tracked_prefixes={}, watch_files=())
    report = build_coverage_report(_payload_with_helper(covered=0, statements=100), baseline)

    assert report["per_file_minimums"] == []
    assert report["baseline"]["regressions"] == []
    assert report["baseline"]["per_file_minimums"] == {}


def test_load_coverage_baseline_reads_per_file_minimums(tmp_path) -> None:
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text(
        json.dumps({"coverage": {"minimum_total_percent": 89.5, "per_file_minimums": {_HELPER: 30.0}}}),
        encoding="utf-8",
    )

    baseline = _load_coverage_baseline(tmp_path)

    assert baseline.per_file_minimums == {_HELPER: 30.0}


def test_load_coverage_baseline_ignores_non_numeric_per_file_minimums(tmp_path) -> None:
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text(
        json.dumps({"coverage": {"per_file_minimums": {_HELPER: "high"}}}),
        encoding="utf-8",
    )

    baseline = _load_coverage_baseline(tmp_path)

    assert baseline.per_file_minimums == {}


def test_per_file_rows_render_in_stdout_and_markdown_reports(tmp_path) -> None:
    report = build_coverage_report(
        _payload_with_helper(covered=40, statements=100), _baseline_with_helper(threshold=30.0)
    )

    stdout_lines = _build_stdout(report, reports_path=tmp_path)
    _write_coverage_reports(report_dir=tmp_path, report=report)

    assert any("Per-file minimums:" in line for line in stdout_lines)
    assert any(_HELPER in line and "40.00%" in line for line in stdout_lines)
    summary_md = (tmp_path / "coverage-summary.md").read_text(encoding="utf-8")
    assert "## Per-file minimums" in summary_md
    assert _HELPER in summary_md
    summary_json = json.loads((tmp_path / "coverage-summary.json").read_text(encoding="utf-8"))
    assert summary_json["per_file_minimums"][0]["path"] == _HELPER


def test_coverage_source_measures_installed_helper() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'source = ["keyrgb", "system/bin"]' in text


def test_debt_baseline_tracks_installed_helper_per_file_minimum() -> None:
    payload = json.loads(Path("buildpython/config/debt_baselines.json").read_text(encoding="utf-8"))

    per_file_minimums = payload["coverage"]["per_file_minimums"]
    assert per_file_minimums[_HELPER] == 60.0
    # Existing total/prefix/watch thresholds must not be lowered.
    assert payload["coverage"]["minimum_total_percent"] == 89.5
    assert payload["coverage"]["tracked_prefixes"] == {
        "keyrgb/core/": 89.5,
        "keyrgb/tray/": 88.5,
        "keyrgb/gui/": 90.0,
    }
    assert payload["coverage"]["minimum_watch_file_percent"] == 75.0
