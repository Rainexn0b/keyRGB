from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from buildpython.core import runner
from buildpython.core.model import Step, StepOutcome
from buildpython.utils.subproc import RunResult


def test_is_module_available_checks_module_spec(monkeypatch) -> None:
    monkeypatch.setattr(
        runner.importlib.util,
        "find_spec",
        lambda name: SimpleNamespace() if name == "ruff" else None,
    )

    assert runner._is_module_available("ruff") is True
    assert runner._is_module_available("missing-module") is False


def test_is_module_available_propagates_unexpected_find_spec_failures(monkeypatch) -> None:
    def fake_find_spec(_name: str):
        raise AssertionError("unexpected spec failure")

    monkeypatch.setattr(runner.importlib.util, "find_spec", fake_find_spec)

    with pytest.raises(AssertionError, match="unexpected spec failure"):
        runner._is_module_available("ruff")


def test_ci_environment_detection_honors_standard_flags(monkeypatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert runner._is_ci_environment() is False

    monkeypatch.setenv("CI", "true")
    assert runner._is_ci_environment() is True

    monkeypatch.setenv("CI", "0")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert runner._is_ci_environment() is True


def _steps(tmp_path: Path, *names: str) -> list[Step]:
    return [
        Step(
            number=index,
            name=name,
            description=f"run {name}",
            log_file=tmp_path / f"{name}.log",
            runner=lambda: (_ for _ in ()).throw(AssertionError("step runner should be stubbed")),
        )
        for index, name in enumerate(names, start=1)
    ]


def _capture_runner_summaries(monkeypatch, tmp_path: Path) -> list[object]:
    summaries: list[object] = []
    monkeypatch.setattr(runner, "buildlog_dir", lambda: tmp_path)
    monkeypatch.setattr(runner.summary_module, "write_summary", lambda _path, summary: summaries.append(summary))
    monkeypatch.setattr(runner.summary_module, "build_terminal_build_overview", lambda _path, _summary: [])
    monkeypatch.setattr(runner, "write_debt_index", lambda _path: None)
    return summaries


def test_run_returns_zero_and_writes_passing_summary_when_all_steps_succeed(monkeypatch, tmp_path: Path) -> None:
    summaries = _capture_runner_summaries(monkeypatch, tmp_path)
    calls: list[str] = []

    def fake_run_step(step: Step, **_kwargs) -> StepOutcome:
        calls.append(step.name)
        return StepOutcome(status="success", exit_code=0, duration_s=0.1)

    monkeypatch.setattr(runner, "run_step", fake_run_step)

    exit_code = runner.run(_steps(tmp_path, "one", "two"), verbose=False, continue_on_error=False)

    assert exit_code == 0
    assert calls == ["one", "two"]
    assert summaries[-1].passed is True  # type: ignore[attr-defined]


def test_run_stops_at_first_failure_and_returns_its_exit_code_without_continue(monkeypatch, tmp_path: Path) -> None:
    summaries = _capture_runner_summaries(monkeypatch, tmp_path)
    calls: list[str] = []

    def fake_run_step(step: Step, **_kwargs) -> StepOutcome:
        calls.append(step.name)
        return StepOutcome(status="failure", exit_code=7, duration_s=0.1)

    monkeypatch.setattr(runner, "run_step", fake_run_step)

    exit_code = runner.run(_steps(tmp_path, "one", "two"), verbose=False, continue_on_error=False)

    assert exit_code == 7
    assert calls == ["one"]
    assert summaries[-1].passed is False  # type: ignore[attr-defined]
    assert [step.name for step in summaries[-1].steps] == ["one"]  # type: ignore[attr-defined]


def test_continue_on_error_runs_later_steps_and_writes_failed_summary(monkeypatch, tmp_path: Path) -> None:
    summaries = _capture_runner_summaries(monkeypatch, tmp_path)
    calls: list[str] = []

    outcomes = {
        "one": StepOutcome(status="failure", exit_code=3, duration_s=0.1),
        "two": StepOutcome(status="success", exit_code=0, duration_s=0.1),
    }

    def fake_run_step(step: Step, **_kwargs) -> StepOutcome:
        calls.append(step.name)
        return outcomes[step.name]

    monkeypatch.setattr(runner, "run_step", fake_run_step)

    exit_code = runner.run(_steps(tmp_path, "one", "two"), verbose=False, continue_on_error=True)

    assert exit_code == 3
    assert calls == ["one", "two"]
    assert summaries[-1].passed is False  # type: ignore[attr-defined]
    assert [step.status for step in summaries[-1].steps] == ["failure", "success"]  # type: ignore[attr-defined]


def test_continue_on_error_returns_first_failure_exit_code_after_multiple_failures(monkeypatch, tmp_path: Path) -> None:
    _capture_runner_summaries(monkeypatch, tmp_path)
    outcomes = {
        "one": StepOutcome(status="failure", exit_code=3, duration_s=0.1),
        "two": StepOutcome(status="failure", exit_code=7, duration_s=0.1),
    }
    monkeypatch.setattr(runner, "run_step", lambda step, **_kwargs: outcomes[step.name])

    exit_code = runner.run(_steps(tmp_path, "one", "two"), verbose=False, continue_on_error=True)

    assert exit_code == 3


def test_continue_on_error_returns_zero_when_steps_succeed_or_are_skipped(monkeypatch, tmp_path: Path) -> None:
    _capture_runner_summaries(monkeypatch, tmp_path)
    outcomes = {
        "one": StepOutcome(status="skipped", exit_code=0, duration_s=0.1),
        "two": StepOutcome(status="success", exit_code=0, duration_s=0.1),
    }
    monkeypatch.setattr(runner, "run_step", lambda step, **_kwargs: outcomes[step.name])

    exit_code = runner.run(_steps(tmp_path, "one", "two"), verbose=False, continue_on_error=True)

    assert exit_code == 0


def test_continue_on_error_normalizes_invalid_zero_failure_code(monkeypatch, tmp_path: Path) -> None:
    _capture_runner_summaries(monkeypatch, tmp_path)
    monkeypatch.setattr(
        runner,
        "run_step",
        lambda _step, **_kwargs: StepOutcome(status="failure", exit_code=0, duration_s=0.1),
    )

    exit_code = runner.run(_steps(tmp_path, "one"), verbose=False, continue_on_error=True)

    assert exit_code == 1


def test_ci_output_uses_healthbar_and_keeps_failure_details_in_step_log(monkeypatch, tmp_path: Path, capsys) -> None:
    _capture_runner_summaries(monkeypatch, tmp_path)
    monkeypatch.setenv("CI", "true")
    raw_failure = "first diagnostic\nsecond diagnostic\n"
    step = Step(
        number=1,
        name="Demo",
        description="run demo",
        log_file=tmp_path / "step-01-demo.log",
        runner=lambda: RunResult(command_str="demo", stdout=raw_failure, stderr="", exit_code=7),
    )

    exit_code = runner.run([step], verbose=False, continue_on_error=False)

    output = capsys.readouterr().out
    assert exit_code == 7
    assert "Build health 0/100" in output
    assert "[░░░░░░░░░░░░░░░░░░░░]" in output
    assert raw_failure.strip() not in output
    assert f"→ See {step.log_file}" in output
    assert "first diagnostic" in step.log_file.read_text(encoding="utf-8")


def test_verbose_ci_output_still_prints_failure_details(monkeypatch, tmp_path: Path, capsys) -> None:
    _capture_runner_summaries(monkeypatch, tmp_path)
    monkeypatch.setenv("CI", "true")
    step = Step(
        number=1,
        name="Demo",
        description="run demo",
        log_file=tmp_path / "step-01-demo.log",
        runner=lambda: RunResult(command_str="demo", stdout="full diagnostic\n", stderr="", exit_code=2),
    )

    exit_code = runner.run([step], verbose=True, continue_on_error=False)

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "full diagnostic" in output
    assert "Build health 0/100" not in output
