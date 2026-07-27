from __future__ import annotations

from buildpython.steps import step_format
from buildpython.utils.subproc import RunResult


def test_ruff_format_check_runner_covers_runtime_and_tooling_surfaces(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _run(args, **_kwargs) -> RunResult:
        calls.append(args)
        return RunResult(command_str=" ".join(args), stdout="ok\n", stderr="", exit_code=0)

    monkeypatch.setattr(step_format, "run", _run)
    monkeypatch.setattr(step_format, "python_exe", lambda: "python")

    result = step_format.ruff_format_check_runner()

    assert calls == [
        [
            "python",
            "-m",
            "ruff",
            "format",
            "--check",
            "src",
            "buildpython",
            "scripts/release",
            "tests",
        ]
    ]
    assert result.exit_code == 0
    assert result.stdout == "ok\n"
