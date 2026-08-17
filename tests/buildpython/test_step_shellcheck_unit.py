from __future__ import annotations

from pathlib import Path

from buildpython.steps import step_shellcheck
from buildpython.utils.subproc import RunResult


def test_shellcheck_runner_skips_when_binary_missing(monkeypatch) -> None:
    monkeypatch.setattr(step_shellcheck, "shellcheck_bin", lambda: None)

    result = step_shellcheck.shellcheck_runner()

    assert result.exit_code == 0
    assert "not installed" in result.stdout


def test_shellcheck_runner_invokes_script_list(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []
    for relative in step_shellcheck.shell_scripts():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n", encoding="utf-8")

    def _run(args, **_kwargs) -> RunResult:
        calls.append(args)
        return RunResult(command_str=" ".join(args), stdout="ok\n", stderr="", exit_code=0)

    monkeypatch.setattr(step_shellcheck, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_shellcheck, "shellcheck_bin", lambda: "shellcheck")
    monkeypatch.setattr(step_shellcheck, "run", _run)

    result = step_shellcheck.shellcheck_runner()

    assert result.exit_code == 0
    assert calls[0][0] == "shellcheck"
    assert calls[0][1] == "-x"
    assert calls[0][2:] == [str(Path(path)) for path in step_shellcheck.shell_scripts()]
