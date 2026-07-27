from __future__ import annotations

from buildpython.steps import step_defs
from buildpython.utils.subproc import RunResult


def _ruff_runner():
    return next(step.runner for step in step_defs.steps() if step.name == "Ruff")


def test_ruff_runner_checks_runtime_and_tooling_surfaces(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _run(args, **_kwargs) -> RunResult:
        calls.append(args)
        return RunResult(command_str=" ".join(args), stdout="ok\n", stderr="", exit_code=0)

    monkeypatch.setattr(step_defs, "run", _run)
    monkeypatch.setattr(step_defs, "python_exe", lambda: "python")

    result = _ruff_runner()()

    assert calls == [
        [
            "python",
            "-m",
            "ruff",
            "check",
            "src",
            "buildpython",
            "scripts/release",
            "tests",
        ]
    ]
    assert result.exit_code == 0
    assert result.stdout == "ok\n"
