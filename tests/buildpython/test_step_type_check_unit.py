from __future__ import annotations

from pathlib import Path

from buildpython.steps import step_type_check
from buildpython.utils.subproc import RunResult


def test_mypy_runner_checks_runtime_and_gui(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _run(args, **_kwargs) -> RunResult:
        calls.append(args)
        return RunResult(command_str=" ".join(args), stdout="ok\n", stderr="", exit_code=0)

    monkeypatch.setattr(step_type_check, "run", _run)
    monkeypatch.setattr(step_type_check, "python_exe", lambda: "python")

    result = step_type_check.mypy_runner()

    assert calls == [
        [
            "python",
            "-m",
            "mypy",
            "keyrgb/core",
            "keyrgb/tray",
            "keyrgb/gui",
            "buildpython",
            "scripts/release",
            "scripts/dependency_audit.py",
            "tests/buildpython",
            "system/bin/keyrgb-power-helper",
        ]
    ]
    assert result.exit_code == 0
    assert result.stdout == "ok\n"


def test_mypy_runner_propagates_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        step_type_check,
        "run",
        lambda *_args, **_kwargs: RunResult(command_str="mypy", stdout="", stderr="type error", exit_code=1),
    )

    result = step_type_check.mypy_runner()

    assert result.command_str == "mypy"
    assert result.stderr == "type error"
    assert result.exit_code == 1


def test_mypy_config_skips_host_numpy_stubs() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'python_version = "3.10"' in text
    assert "explicit_package_bases = true" in text
    assert (
        """
[[tool.mypy.overrides]]
module = [
    "numpy",
    "numpy.*",
]
follow_imports = "skip"
""".strip()
        in text
    )
