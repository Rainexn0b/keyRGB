from __future__ import annotations

from buildpython.utils.import_probe import probe_module_import
from buildpython.utils.subproc import RunResult

import buildpython.utils.import_probe as import_probe


def test_probe_module_import_returns_success_when_subprocess_succeeds(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        import_probe,
        "run",
        lambda args, *, cwd, env_overrides=None: RunResult(
            command_str=" ".join(args),
            stdout="",
            stderr="",
            exit_code=0,
        ),
    )

    result = probe_module_import("src.tray.entrypoint", cwd=tmp_path)

    assert result.ok is True
    assert result.module == "src.tray.entrypoint"
    assert result.stderr == ""


def test_probe_module_import_extracts_exception_type_and_message(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        import_probe,
        "run",
        lambda args, *, cwd, env_overrides=None: RunResult(
            command_str=" ".join(args),
            stdout="",
            stderr="Traceback (most recent call last):\nRuntimeError: optional boom\n",
            exit_code=1,
        ),
    )

    result = probe_module_import("gi", cwd=tmp_path)

    assert result.ok is False
    assert result.error_type == "RuntimeError"
    assert result.error_message == "optional boom"
    assert result.failure_detail == "RuntimeError: optional boom"


def test_probe_module_import_handles_error_lines_without_message(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        import_probe,
        "run",
        lambda args, *, cwd, env_overrides=None: RunResult(
            command_str=" ".join(args),
            stdout="",
            stderr="Traceback (most recent call last):\nKeyboardInterrupt\n",
            exit_code=1,
        ),
    )

    result = probe_module_import("interrupting_mod", cwd=tmp_path)

    assert result.ok is False
    assert result.error_type == "KeyboardInterrupt"
    assert result.error_message == ""
    assert result.failure_detail == "KeyboardInterrupt"