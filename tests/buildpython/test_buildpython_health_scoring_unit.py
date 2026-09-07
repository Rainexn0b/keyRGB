from __future__ import annotations

import json

import pytest

from buildpython.core.runner_support.health import build_step_health


def _write_report(tmp_path, name: str, payload: dict[str, object]) -> None:
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")


def test_unscored_step_has_no_healthbar_metric(tmp_path) -> None:
    assert build_step_health("Compile", stdout="", stderr="", report_dir=tmp_path, failed=False) is None


def test_stale_structured_report_does_not_produce_healthbar(tmp_path) -> None:
    _write_report(tmp_path, "coverage-summary.json", {"summary": {"total_percent": 99.0}})

    health = build_step_health(
        "Coverage",
        stdout="",
        stderr="",
        report_dir=tmp_path,
        failed=False,
        started_at=(tmp_path / "coverage-summary.json").stat().st_mtime + 1,
    )

    assert health is None


def test_pytest_health_uses_pass_rate_and_caps_failed_gate(tmp_path) -> None:
    passing = build_step_health(
        "Pytest",
        stdout="18 passed, 2 skipped in 0.20s\n",
        stderr="",
        report_dir=tmp_path,
        failed=False,
    )
    failing = build_step_health(
        "Pytest",
        stdout="8 passed, 2 failed in 0.20s\n",
        stderr="",
        report_dir=tmp_path,
        failed=True,
    )

    assert passing is not None and (passing.label, passing.score) == ("Test Health", 100)
    assert failing is not None and (failing.label, failing.score) == ("Test Health", 49)


def test_file_size_health_applies_weighted_debt_penalties_and_failure_cap(tmp_path) -> None:
    _write_report(
        tmp_path,
        "file-size-analysis.json",
        {
            "counts": {
                "file_lines": {"refactor": 1, "critical": 1, "severe": 0, "extreme": 0},
                "import_block_lines": {"warning": 4, "critical": 0, "severe": 0},
                "flat_directories": 2,
                "delegation_candidates": 0,
                "middleman_modules": 1,
                "unreferenced_files": 0,
            }
        },
    )

    passing = build_step_health("File Size", stdout="", stderr="", report_dir=tmp_path, failed=False)
    failing = build_step_health("File Size", stdout="", stderr="", report_dir=tmp_path, failed=True)

    assert passing is not None and passing.score == 79
    assert failing is not None and failing.score == 49


def test_loc_health_penalizes_monitor_lightly_and_gated_buckets_heavily(tmp_path) -> None:
    _write_report(
        tmp_path,
        "loc-check.json",
        {"counts": {"monitor": 20, "refactor": 1, "critical": 1, "severe": 0}},
    )

    health = build_step_health("LOC Check", stdout="", stderr="", report_dir=tmp_path, failed=False)

    assert health is not None and (health.label, health.score) == ("LOC Health", 78)


def test_coverage_health_uses_actual_percentage_and_caps_regressions(tmp_path) -> None:
    _write_report(tmp_path, "coverage-summary.json", {"summary": {"total_percent": 90.25}})

    passing = build_step_health("Coverage", stdout="", stderr="", report_dir=tmp_path, failed=False)
    failing = build_step_health("Coverage", stdout="", stderr="", report_dir=tmp_path, failed=True)

    assert passing is not None and passing.score == 90
    assert failing is not None and failing.score == 49


def test_dead_code_health_scores_only_actionable_findings(tmp_path) -> None:
    _write_report(tmp_path, "dead-code-vulture.json", {"count": 29, "actionable_count": 2})

    health = build_step_health("Dead Code", stdout="", stderr="", report_dir=tmp_path, failed=False)

    assert health is not None and health.score == 60


@pytest.mark.parametrize(
    ("step_name", "report_name", "payload", "expected_score"),
    [
        (
            "Code Markers",
            "code-markers.json",
            {
                "marker_counts": {"TODO": 1, "FIXME": 0, "HACK": 1, "NOTE": 50},
                "baseline": {"gated_markers": ["TODO", "FIXME", "HACK"]},
            },
            60,
        ),
        (
            "Code Hygiene",
            "code-hygiene.json",
            {"active_counts": {"forbidden_api": 1, "cleanup_hotspot": 2}},
            72,
        ),
        (
            "Architecture Validation",
            "architecture-validation.json",
            {"summary": {"errors": 1, "warnings": 2}},
            65,
        ),
        (
            "Exception Transparency",
            "exception-transparency.json",
            {"counts": {"naked_except": 1, "broad_except_unlogged": 1}},
            50,
        ),
    ],
)
def test_structured_health_scores_apply_category_weights(
    tmp_path, step_name: str, report_name: str, payload: dict[str, object], expected_score: int
) -> None:
    _write_report(tmp_path, report_name, payload)

    health = build_step_health(step_name, stdout="", stderr="", report_dir=tmp_path, failed=False)

    assert health is not None and health.score == expected_score
