from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

import pytest

from keyrgb.core.diagnostics import runtime_capture


def test_runtime_environment_selects_exact_debug_mode() -> None:
    env = runtime_capture._runtime_environment(
        mode="debug",
        environ={
            "HOME": "/tmp/example",
            "KEYRGB_DEBUG_BRIGHTNESS": "1",
            "KEYRGB_DEBUG_REACTIVE_INPUT": "1",
        },
    )

    assert env == {
        "HOME": "/tmp/example",
        "KEYRGB_DEBUG": "1",
        "PYTHONUNBUFFERED": "1",
    }


def test_runtime_environment_full_mode_enables_all_debug_flags() -> None:
    env = runtime_capture._runtime_environment(mode="full", environ={})

    assert env == {
        "KEYRGB_DEBUG": "1",
        "KEYRGB_DEBUG_BRIGHTNESS": "1",
        "KEYRGB_DEBUG_REACTIVE_INPUT": "1",
        "PYTHONUNBUFFERED": "1",
    }


def test_discover_source_root_prefers_checkout_cwd(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "keyrgb" / "tray").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.setattr(runtime_capture.Path, "cwd", lambda: tmp_path)

    assert runtime_capture.discover_source_root() == tmp_path.resolve()


def test_source_runtime_uses_active_python_without_external_runtime(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runtime_capture.shutil, "which", lambda _name: None)
    monkeypatch.setattr(runtime_capture.os, "get_exec_path", list)

    assert runtime_capture._runtime_command(launcher="source", source_root=tmp_path) == [
        sys.executable,
        "-B",
        "-u",
        "-m",
        "keyrgb.tray",
    ]


def test_source_runtime_uses_active_python_even_when_appimage_is_on_path(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    external_launcher = tmp_path / "bin" / "keyrgb"
    external_launcher.parent.mkdir()
    external_launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(runtime_capture.shutil, "which", lambda _name: str(external_launcher))

    assert runtime_capture._runtime_command(launcher="source", source_root=root) == [
        sys.executable,
        "-B",
        "-u",
        "-m",
        "keyrgb.tray",
    ]


def test_source_runtime_requires_detectable_checkout() -> None:
    with pytest.raises(runtime_capture.RuntimeLogCaptureError, match="No KeyRGB source checkout"):
        runtime_capture._runtime_command(launcher="source", source_root=None)


def test_source_runtime_environment_prepends_checkout_to_pythonpath(tmp_path: Path) -> None:
    env = runtime_capture._runtime_environment(
        mode="debug",
        environ={"PYTHONPATH": "/existing/path"},
        source_root=tmp_path,
    )

    assert env["PYTHONPATH"] == f"{tmp_path.resolve()}{runtime_capture.os.pathsep}/existing/path"


def test_runtime_working_directory_separates_source_and_installed_code(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    command = [str(tmp_path / "bin" / "keyrgb")]

    assert (
        runtime_capture._runtime_working_directory(launcher="source", command=command, source_root=root)
        == root.resolve()
    )
    assert (
        runtime_capture._runtime_working_directory(launcher="installed", command=command, source_root=root)
        == (tmp_path / "bin").resolve()
    )


def test_installed_runtime_rejects_source_checkout_launcher(tmp_path: Path, monkeypatch) -> None:
    source_launcher = tmp_path / "keyrgb"
    source_launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(runtime_capture.shutil, "which", lambda _name: str(source_launcher))
    monkeypatch.setattr(runtime_capture.os, "get_exec_path", list)

    with pytest.raises(runtime_capture.RuntimeLogCaptureError, match="inside this source checkout"):
        runtime_capture._runtime_command(launcher="installed", source_root=tmp_path)


def test_installed_runtime_skips_checkout_launcher_for_external_runtime(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    source_launcher = root / "bin" / "keyrgb"
    source_launcher.parent.mkdir(parents=True)
    source_launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    source_launcher.chmod(0o755)
    external_launcher = tmp_path / "external-bin" / "keyrgb"
    external_launcher.parent.mkdir()
    external_launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    external_launcher.chmod(0o755)
    monkeypatch.setattr(runtime_capture.shutil, "which", lambda _name: str(source_launcher))
    monkeypatch.setattr(
        runtime_capture.os,
        "get_exec_path",
        lambda: [str(source_launcher.parent), str(external_launcher.parent)],
    )

    assert runtime_capture._runtime_command(launcher="installed", source_root=root) == [
        str(external_launcher.resolve())
    ]


def test_capture_runtime_log_truncates_file_and_merges_child_output(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / runtime_capture.RUNTIME_LOG_NAME
    log_path.write_text("stale capture\n", encoding="utf-8")
    calls: list[dict[str, object]] = []

    class _FakeProcess:
        pass

    def _fake_popen(command, **kwargs):
        calls.append({"command": list(command), **kwargs})
        kwargs["stdout"].write("child output\n")
        kwargs["stdout"].flush()
        return _FakeProcess()

    monkeypatch.setattr(runtime_capture, "_runtime_command", lambda **_kwargs: ["/opt/keyrgb"])
    monkeypatch.setattr(runtime_capture, "_runtime_working_directory", lambda **_kwargs: tmp_path)
    monkeypatch.setattr(runtime_capture.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(runtime_capture, "_wait_with_signal_forwarding", lambda _process: 0)

    assert (
        runtime_capture.capture_runtime_log(
            mode="brightness",
            launcher="installed",
            output_directory=tmp_path,
            source_root=tmp_path,
        )
        == 0
    )

    content = log_path.read_text(encoding="utf-8")
    assert "stale capture" not in content
    assert "mode=brightness" in content
    assert "launcher=installed" in content
    assert f"working_directory={tmp_path}" in content
    assert "KEYRGB_DEBUG=1 KEYRGB_DEBUG_BRIGHTNESS=1" in content
    assert content.endswith("--- KeyRGB output ---\nchild output\n")
    assert calls[0]["command"] == ["/opt/keyrgb"]
    assert calls[0]["cwd"] == str(tmp_path)
    assert calls[0]["stderr"] is subprocess.STDOUT
    assert calls[0]["start_new_session"] is True
    child_env = calls[0]["env"]
    assert isinstance(child_env, dict)
    assert child_env["PYTHONUNBUFFERED"] == "1"


def test_capture_source_runtime_uses_checkout_cwd_and_pythonpath(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class _FakeProcess:
        pass

    def _fake_popen(command, **kwargs):
        calls.append({"command": list(command), **kwargs})
        return _FakeProcess()

    monkeypatch.setattr(runtime_capture, "_runtime_command", lambda **_kwargs: ["/opt/keyrgb"])
    monkeypatch.setattr(runtime_capture.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(runtime_capture, "_wait_with_signal_forwarding", lambda _process: 0)

    assert (
        runtime_capture.capture_runtime_log(
            mode="full",
            launcher="source",
            output_directory=tmp_path,
            source_root=tmp_path,
        )
        == 0
    )

    assert calls[0]["cwd"] == str(tmp_path.resolve())
    child_env = calls[0]["env"]
    assert isinstance(child_env, dict)
    assert child_env["PYTHONPATH"].split(runtime_capture.os.pathsep, 1)[0] == str(tmp_path.resolve())


def test_capture_runtime_log_from_cli_dispatches_source_mode(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        runtime_capture,
        "capture_runtime_log",
        lambda *, mode, launcher: calls.append((mode, launcher)) or 17,
    )

    assert (
        runtime_capture.capture_runtime_log_from_cli(
            ["--capture-runtime-log=brightness", "--runtime-log-launcher=source"]
        )
        == 17
    )
    assert calls == [("brightness", "source")]


def test_capture_runtime_log_from_cli_ignores_normal_tray_launch() -> None:
    assert runtime_capture.capture_runtime_log_from_cli([]) is None


def test_capture_runtime_log_from_cli_rejects_launcher_without_capture() -> None:
    with pytest.raises(SystemExit) as exc_info:
        runtime_capture.capture_runtime_log_from_cli(["--runtime-log-launcher=source"])

    assert exc_info.value.code == 2


def test_wait_forwards_interrupt_and_normalizes_signal_exit(monkeypatch) -> None:
    installed_handlers = {}
    restored_handlers = []
    forwarded = []

    def _fake_signal(signum, handler):
        if callable(handler):
            installed_handlers[signum] = handler
        else:
            restored_handlers.append((signum, handler))

    monkeypatch.setattr(runtime_capture.signal, "getsignal", lambda signum: f"previous-{signum}")
    monkeypatch.setattr(runtime_capture.signal, "signal", _fake_signal)
    monkeypatch.setattr(runtime_capture.os, "killpg", lambda pid, signum: forwarded.append((pid, signum)))

    class _FakeProcess:
        pid = 4321

        @staticmethod
        def poll():
            return None

        @staticmethod
        def wait():
            installed_handlers[signal.SIGINT](signal.SIGINT, None)
            return -signal.SIGTERM

    assert runtime_capture._wait_with_signal_forwarding(_FakeProcess()) == 143
    assert forwarded == [(4321, signal.SIGINT)]
    assert restored_handlers == [
        (signal.SIGINT, f"previous-{signal.SIGINT}"),
        (signal.SIGTERM, f"previous-{signal.SIGTERM}"),
    ]
