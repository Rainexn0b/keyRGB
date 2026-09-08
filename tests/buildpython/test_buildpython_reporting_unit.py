from __future__ import annotations

import fcntl
import json
from pathlib import Path

import pytest

from buildpython.core import runner
from buildpython.core.model import Step
from buildpython.core.runner_support import display
from buildpython.steps.coverage_step.constants import _CAPTURE_MARKER_NAME
from buildpython.utils.subproc import RunResult


@pytest.fixture
def reports(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "buildlog_dir", lambda: tmp_path)
    monkeypatch.setattr(display, "buildlog_dir", lambda: tmp_path)
    monkeypatch.setattr(runner, "_is_module_available", lambda _module: True)
    return tmp_path


def _step(directory: Path, name: str, result: RunResult, *, number: int = 1) -> Step:
    return Step(number=number, name=name, description=name, log_file=directory / f"{number}.log", runner=lambda: result)


def _result(*, stdout="", exit_code=0, skip_reason="") -> RunResult:
    return RunResult(
        command_str="fixture command", stdout=stdout, stderr="", exit_code=exit_code, skip_reason=skip_reason
    )


def _summary(directory: Path) -> dict:
    return json.loads((directory / "build-summary.json").read_text())


def test_concurrent_writer_is_rejected_without_overwriting_current_run(reports, capsys) -> None:
    summary_path = reports / "build-summary.json"
    summary_path.write_text('{"run_id": "first-writer"}')
    with (reports / ".buildpython.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert runner.run([_step(reports, "Compile", _result())], verbose=False, continue_on_error=False) == 2
    assert _summary(reports) == {"run_id": "first-writer"}
    assert "Build not started" in capsys.readouterr().out


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("errors,warnings", [(0, 0), (0, 2), (1, 0)])
def test_architecture_prints_penalty_score_alongside_counts_and_gate_status(
    reports, capsys, errors, warnings, verbose
) -> None:

    def scan():
        (reports / "architecture-validation.json").write_text(
            json.dumps(
                {
                    "summary": {
                        "rules_checked": 24,
                        "scanned_files": 610,
                        "errors": errors,
                        "warnings": warnings,
                        "findings": errors + warnings,
                    }
                }
            )
        )
        return _result(exit_code=errors)

    step = Step(17, "Architecture Validation", "scan", reports / "17.log", scan)
    assert runner.run([step], verbose=verbose, continue_on_error=False) == errors
    output = capsys.readouterr().out
    assert f"Rules checked: 24 | Files scanned: 610 | Errors: {errors}" in output
    assert "Architecture Health:" in output
    score = 100 - errors * 25 - warnings * 5
    assert f"{score}% (penalty score)" in output
    assert output.count("Architecture Health:") == 1
    assert "█" in output
    summary = _summary(reports)
    assert "health_score" not in summary
    assert summary["steps"][0]["health"]["score"] == score
    assert f"| {score}% |" in (reports / "build-summary.md").read_text()
    assert summary["passed"] is (not errors)
    assert summary["report_names"] == ["architecture-validation.json"]
    assert "Architecture" not in (reports / "build-summary.md").read_text().split("| Step")[0]


@pytest.mark.parametrize("exit_code", [0, 1])
def test_coverage_reports_measured_percentage_even_when_gate_fails(reports, capsys, exit_code) -> None:
    def coverage():
        (reports / "coverage-summary.json").write_text(json.dumps({"summary": {"total_percent": 90.25}}))
        return _result(exit_code=exit_code)

    assert (
        runner.run(
            [Step(18, "Coverage", "coverage", reports / "18.log", coverage)], verbose=False, continue_on_error=False
        )
        == exit_code
    )
    output = capsys.readouterr().out
    assert "90.25%" in output
    assert "49%" not in output and "Health" not in output


@pytest.mark.parametrize(
    "stdout",
    [
        "2 failed, 8 passed, 1 skipped, 3 warnings in 0.25s\n",
        "8 passed, 2 failed, 1 skipped, 3 warnings in 0.25s\n",
        "1 error, 3 deselected in 0.25s\n",
        "1 skipped, 2 xfailed, 1 xpassed in 0.25s\n",
    ],
)
def test_pytest_highlight_keeps_every_summary_outcome(stdout) -> None:
    assert display._extract_pytest_highlight(stdout, "") == "Tests: " + stdout.split(" in ")[0]


@pytest.mark.parametrize("all_skipped", [False, True])
def test_optional_skips_are_not_a_complete_pass_in_terminal_or_reports(reports, capsys, all_skipped) -> None:
    steps = [_step(reports, "AppImage Smoke", _result(skip_reason="Docker unavailable"))]
    if not all_skipped:
        steps.append(_step(reports, "Compile", _result(), number=2))
    assert runner.run(steps, verbose=False, continue_on_error=False) == 0
    output = capsys.readouterr().out
    expected = "not_run" if all_skipped else "partial"
    summary = _summary(reports)
    assert summary["status"] == expected and summary["passed"] is False
    assert summary["exit_code"] == 0
    assert "NOT RUN" in output if all_skipped else "PARTIAL" in output
    assert "Docker unavailable" in output
    assert "Docker unavailable" in (reports / "build-summary.md").read_text()
    assert "Status: skipped" in (reports / "1.log").read_text()


def test_missing_optional_tool_is_logged_as_not_executed(reports, monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "_is_module_available", lambda _module: False)
    assert runner.run([_step(reports, "Ruff", _result(exit_code=99))], verbose=False, continue_on_error=False) == 0
    assert _summary(reports)["steps"][0]["message"] == "ruff not installed"
    assert "Command: (not executed)" in (reports / "1.log").read_text()
    assert "NOT RUN" in capsys.readouterr().out


def test_fail_fast_keeps_unexecuted_selected_steps_in_denominator(reports, capsys) -> None:
    steps = [_step(reports, "First", _result(exit_code=7)), _step(reports, "Second", _result(), number=2)]
    assert runner.run(steps, verbose=False, continue_on_error=False) == 7
    summary = _summary(reports)
    assert summary["counts"] == {"success": 0, "failure": 1, "skipped": 0, "not_run": 1, "running": 0}
    assert summary["steps"][1]["exit_code"] is None
    assert summary["steps"][1]["log_file"] == ""
    assert "2 selected" in capsys.readouterr().out


def test_continue_on_error_points_to_each_failed_step_log(reports, capsys) -> None:
    steps = [_step(reports, "First", _result(exit_code=7)), _step(reports, "Second", _result(), number=2)]
    assert runner.run(steps, verbose=False, continue_on_error=True) == 7
    assert f"Failure details: {reports / '1.log'}" in capsys.readouterr().out
    assert _summary(reports)["counts"]["success"] == 1


def test_failed_build_cannot_smoke_test_an_old_appimage(reports) -> None:
    steps = [_step(reports, "AppImage", _result(exit_code=7)), _step(reports, "AppImage Smoke", _result(), number=2)]
    assert runner.run(steps, verbose=False, continue_on_error=True) == 7
    smoke_result = _summary(reports)["steps"][1]
    assert smoke_result["status"] == "skipped"
    assert "older artifact" in smoke_result["message"]


def test_unselected_old_reports_do_not_appear_in_current_outputs(reports, capsys) -> None:
    (reports / "coverage-summary.json").write_text(json.dumps({"summary": {"total_percent": 99.99}}))
    (reports / "architecture-validation.json").write_text(json.dumps({"summary": {"errors": 0}}))
    assert runner.run([_step(reports, "Compile", _result())], verbose=False, continue_on_error=False) == 0
    assert "99.99" not in capsys.readouterr().out
    assert "99.99" not in (reports / "build-summary.md").read_text()
    assert json.loads((reports / "debt-index.json").read_text())["sections"] == {}
    assert _summary(reports)["report_names"] == []


@pytest.mark.parametrize("prior_report", [None, "{}", "not json"])
def test_successful_exit_without_a_new_required_report_fails(reports, capsys, prior_report) -> None:
    if prior_report is not None:
        (reports / "architecture-validation.json").write_text(prior_report)
    assert (
        runner.run([_step(reports, "Architecture Validation", _result())], verbose=False, continue_on_error=False) == 1
    )
    assert _summary(reports)["passed"] is False
    assert "Expected fresh JSON report" in (reports / "1.log").read_text()
    assert "Rules checked:" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "problem, code", [(AssertionError("unexpected fixture bug"), 1), (SystemExit(2), 2), (KeyboardInterrupt(), 130)]
)
def test_abort_replaces_previous_success_and_records_traceback(reports, problem, code) -> None:
    (reports / "build-summary.json").write_text('{"passed": true}')
    (reports / "1.log").write_text("old success")

    def crash():
        raise problem

    with pytest.raises(type(problem)):
        runner.run([Step(1, "Broken", "broken", reports / "1.log", crash)], verbose=False, continue_on_error=False)
    summary = _summary(reports)
    assert summary["status"] == "incomplete" and summary["passed"] is False
    assert summary["exit_code"] is None
    assert summary["steps"][0]["status"] == "running"
    assert "Status: aborted" in (reports / "1.log").read_text()
    assert "Traceback" in (reports / "1.log").read_text()
    assert f"Exit Code: {code}" in (reports / "1.log").read_text()


def test_build_invalidates_previous_pytest_capture_marker(reports) -> None:
    marker = reports / _CAPTURE_MARKER_NAME
    marker.write_text("old capture")

    def check():
        assert not marker.exists()
        return _result()

    assert (
        runner.run([Step(1, "Check", "check", reports / "1.log", check)], verbose=False, continue_on_error=False) == 0
    )
