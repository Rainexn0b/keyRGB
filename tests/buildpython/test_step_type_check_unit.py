from __future__ import annotations

from buildpython.steps import step_type_check
from buildpython.utils.subproc import RunResult


def test_mypy_runner_checks_runtime_and_narrow_gui_baseline(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _run(args, **_kwargs) -> RunResult:
        calls.append(args)
        return RunResult(command_str=" ".join(args), stdout="ok\n", stderr="", exit_code=0)

    monkeypatch.setattr(step_type_check, "run", _run)
    monkeypatch.setattr(step_type_check, "python_exe", lambda: "python")

    result = step_type_check.mypy_runner()

    assert calls[0] == ["python", "-m", "mypy", "src/core", "src/tray", "buildpython"]
    assert calls[1][:5] == ["python", "-m", "mypy", "--follow-imports=skip", "src/gui/perkey/ops/color_map_ops.py"]
    assert tuple(calls[1][4:]) == step_type_check._GUI_PURE_MYPY_TARGETS
    assert result.exit_code == 0
    assert result.stdout == "ok\nok\n"


def test_mypy_runner_propagates_gui_baseline_failure(monkeypatch) -> None:
    results = iter(
        [
            RunResult(command_str="runtime", stdout="", stderr="", exit_code=0),
            RunResult(command_str="gui", stdout="", stderr="gui error", exit_code=1),
        ]
    )
    monkeypatch.setattr(step_type_check, "run", lambda *_args, **_kwargs: next(results))

    result = step_type_check.mypy_runner()

    assert result.command_str == "runtime && gui"
    assert result.stderr == "gui error"
    assert result.exit_code == 1
