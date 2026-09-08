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
            "keyrgb",
            "buildpython",
            "scripts/release",
            "scripts/dependency_audit.py",
            "tests",
            "system/bin/keyrgb-power-helper",
        ]
    ]
    assert result.exit_code == 0
    assert result.stdout == "ok\n"


def test_ruff_runner_includes_exact_installed_helper_path() -> None:
    assert step_defs.POWER_HELPER_PATH == "system/bin/keyrgb-power-helper"


def test_compile_runner_byte_compiles_installed_helper_after_keyrgb(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _run(args, **_kwargs) -> RunResult:
        calls.append(args)
        return RunResult(command_str=" ".join(args), stdout="", stderr="", exit_code=0)

    monkeypatch.setattr(step_defs, "run", _run)
    monkeypatch.setattr(step_defs, "python_exe", lambda: "python")

    compile_runner = next(step.runner for step in step_defs.steps() if step.name == "Compile")
    result = compile_runner()

    assert calls == [
        ["python", "-m", "compileall", "-q", "keyrgb"],
        ["python", "-m", "py_compile", "system/bin/keyrgb-power-helper"],
    ]
    assert result.exit_code == 0


def test_compile_runner_fails_when_helper_has_syntax_error(monkeypatch) -> None:
    def _run(args, **_kwargs) -> RunResult:
        if "py_compile" in args:
            return RunResult(command_str=" ".join(args), stdout="", stderr="SyntaxError", exit_code=1)
        return RunResult(command_str=" ".join(args), stdout="", stderr="", exit_code=0)

    monkeypatch.setattr(step_defs, "run", _run)
    monkeypatch.setattr(step_defs, "python_exe", lambda: "python")

    compile_runner = next(step.runner for step in step_defs.steps() if step.name == "Compile")
    result = compile_runner()

    assert result.exit_code == 1
    assert result.stderr == "SyntaxError"
