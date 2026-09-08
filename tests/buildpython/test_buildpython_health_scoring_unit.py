from __future__ import annotations

import json

import pytest

from buildpython.core.runner_support.health import build_step_health


@pytest.mark.parametrize(
    "step,report,payload,score",
    [
        ("Architecture Validation", "architecture-validation.json", {"summary": {"errors": 1, "warnings": 2}}, 65),
        (
            "Code Markers",
            "code-markers.json",
            {"marker_counts": {"TODO": 2, "NOTE": 50}, "baseline": {"gated_markers": ["TODO"]}},
            60,
        ),
        (
            "File Size",
            "file-size-analysis.json",
            {"counts": {"file_lines": {"refactor": 1}, "import_block_lines": {"warning": 1}}},
            96.5,
        ),
        ("LOC Check", "loc-check.json", {"counts": {"monitor": 48, "refactor": 1}}, 83),
        ("Code Hygiene", "code-hygiene.json", {"active_counts": {"forbidden_api": 1, "cleanup_hotspot": 2}}, 72),
        (
            "Exception Transparency",
            "exception-transparency.json",
            {"counts": {"naked_except": 1, "broad_except_unlogged": 1}, "waived_total": 30},
            50,
        ),
        ("Dead Code", "dead-code-vulture.json", {"actionable_count": 2, "count": 100}, 60),
    ],
)
@pytest.mark.parametrize("failed", [False, True])
def test_penalties_are_independent_of_gate_status(tmp_path, step, report, payload, score, failed) -> None:
    (tmp_path / report).write_text(json.dumps(payload))
    health = build_step_health(step, stdout="", stderr="", report_dir=tmp_path, report_names=(report,), failed=failed)
    assert health is not None and health.score == score
    assert build_step_health(step, stdout="", stderr="", report_dir=tmp_path, failed=failed) is None


@pytest.mark.parametrize(
    "errors,warnings,expected", [(0, 0, 100), (0, 1, 95), (0, 2, 90), (1, 0, 75), (2, 0, 50), (10, 8, 0)]
)
def test_each_architecture_occurrence_deducts_and_score_stops_at_zero(tmp_path, errors, warnings, expected) -> None:
    name = "architecture-validation.json"
    (tmp_path / name).write_text(json.dumps({"summary": {"errors": errors, "warnings": warnings}}))
    health = build_step_health(
        "Architecture Validation", stdout="", stderr="", report_dir=tmp_path, report_names=(name,), failed=False
    )
    assert health is not None and health.score == expected


@pytest.mark.parametrize(
    "step,output,failed,score",
    [
        ("Ruff", "All checks passed!", False, 100),
        ("Ruff", "All checks passed!", True, None),
        ("Ruff", "Found 1 error.", True, 95),
        ("Ruff", "source excerpt\nFound 2 errors.\n[*] 2 fixable", True, 90),
        ("Ruff", "Found 40 errors.", True, 0),
        ("Ruff", "error: invalid configuration", True, None),
        ("Type Check", "Success: no issues found in 610 source files", False, 100),
        (
            "Type Check",
            "a.py:1: error: first\na.py:2: error: second\nFound 2 errors in 1 file (checked 610 source files)",
            True,
            80,
        ),
        ("Type Check", "Found 1 error in 1 file (errors prevented further checking)", True, 90),
        ("Type Check", "INTERNAL ERROR", True, None),
        ("Type Check", "", False, None),
        ("Compile", "", False, None),
        ("Pytest", "8 passed, 2 failed in 1.0s", True, None),
        ("Coverage", "", False, None),
    ],
)
def test_tool_summaries_count_occurrences_once_and_do_not_score_missing_results(
    tmp_path, step, output, failed, score
) -> None:
    health = build_step_health(step, stdout="", stderr=output, report_dir=tmp_path, failed=failed)
    assert (health.score if health is not None else None) == score


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"summary": {}},
        {"summary": {"rules_checked": 24}},
        {"summary": {"errors": -1, "warnings": 0}},
        {"summary": {"errors": "unknown", "warnings": 0}},
    ],
)
def test_missing_or_invalid_counts_do_not_default_to_perfect_health(tmp_path, payload) -> None:
    name = "architecture-validation.json"
    (tmp_path / name).write_text(json.dumps(payload))
    assert (
        build_step_health(
            "Architecture Validation", stdout="", stderr="", report_dir=tmp_path, report_names=(name,), failed=False
        )
        is None
    )
