from __future__ import annotations

from types import SimpleNamespace

import pytest

from buildpython.core import cli


@pytest.mark.parametrize("mode", ["debug", "brightness", "full"])
def test_capture_runtime_log_dispatches_selected_mode(monkeypatch, mode: str) -> None:
    calls: list[tuple[str, str]] = []

    def _capture_runtime_log(*, mode: str, launcher: str) -> int:
        calls.append((mode, launcher))
        return 17

    monkeypatch.setattr(cli, "capture_runtime_log", _capture_runtime_log)
    monkeypatch.setattr(cli, "run", lambda *_args, **_kwargs: pytest.fail("build runner called"))

    assert cli.main([f"--capture-runtime-log={mode}"]) == 17
    assert calls == [(mode, "installed")]


def test_capture_runtime_log_without_value_defaults_to_full(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def _capture_runtime_log(*, mode: str, launcher: str) -> int:
        calls.append((mode, launcher))
        return 0

    monkeypatch.setattr(cli, "capture_runtime_log", _capture_runtime_log)

    assert cli.main(["--capture-runtime-log", "--runtime-log-launcher=source"]) == 0
    assert calls == [("full", "source")]


@pytest.mark.parametrize(
    "conflict",
    [
        "--profile=quick",
        "--list-profiles",
        "--list-steps",
        "--run-steps=1",
        "--skip-steps=1",
        "--verbose",
        "--continue-on-error",
        "--with-appimage",
        "--with-black",
    ],
)
def test_capture_runtime_log_rejects_build_options(conflict: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--capture-runtime-log", conflict])

    assert exc_info.value.code == 2


def test_runtime_log_launcher_requires_capture_mode() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--runtime-log-launcher=source"])

    assert exc_info.value.code == 2


def test_capture_runtime_log_rejects_unknown_mode() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--capture-runtime-log=everything"])

    assert exc_info.value.code == 2


def test_build_cli_propagates_runner_failure_with_continue_on_error(monkeypatch) -> None:
    selected_step = SimpleNamespace(number=1, name="Compile")
    calls: list[tuple[object, bool, bool]] = []
    monkeypatch.setattr(cli, "_select_steps", lambda **_kwargs: [selected_step])

    def fake_run(selected, *, verbose: bool, continue_on_error: bool) -> int:
        calls.append((selected, verbose, continue_on_error))
        return 9

    monkeypatch.setattr(cli, "run", fake_run)

    exit_code = cli.main(["--run-steps=1", "--continue-on-error"])

    assert exit_code == 9
    assert calls == [([selected_step], False, True)]
