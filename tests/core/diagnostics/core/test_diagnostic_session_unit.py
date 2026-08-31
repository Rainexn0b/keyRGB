from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import keyrgb.core.diagnostics as diagnostics_pkg
from keyrgb.core.diagnostics import (
    diagnostic_session,
    diagnostic_session_evidence as dsev,
    runtime_capture as rc_module,
)


def test_select_session_launcher_auto_picks_source_from_checkout() -> None:
    assert diagnostic_session._select_session_launcher(None, Path("/checkout")) == "source"
    assert diagnostic_session._select_session_launcher(None, None) == "installed"


def test_select_session_launcher_honors_override() -> None:
    assert diagnostic_session._select_session_launcher("installed", Path("/checkout")) == "installed"
    assert diagnostic_session._select_session_launcher("source", None) == "source"


def test_diagnostic_child_command_avoids_appimage_recursion(monkeypatch, tmp_path: Path) -> None:
    source_root = tmp_path / "repo"
    external_launcher = tmp_path / "external" / "bin" / "keyrgb"
    external_launcher.parent.mkdir(parents=True)
    external_launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    external_launcher.chmod(0o755)
    # _installed_runtime_command resolves launchers from runtime_capture's globals.
    monkeypatch.setattr(rc_module.shutil, "which", lambda _name: str(external_launcher))
    monkeypatch.setattr(
        rc_module.os,
        "get_exec_path",
        lambda: [str(external_launcher.parent)],
    )

    # Installed mode resolves the external launcher when not in an AppImage.
    assert diagnostic_session._diagnostic_child_command(
        launcher="installed", source_root=source_root, appimage_active=False
    ) == [str(external_launcher.resolve())]

    # Source mode uses the active interpreter module form.
    assert diagnostic_session._diagnostic_child_command(
        launcher="source", source_root=source_root, appimage_active=False
    ) == [sys.executable, "-B", "-u", "-m", "keyrgb.tray"]

    # Inside an AppImage the child must use the current Python rather than
    # re-resolving `keyrgb` from PATH (which would re-mount the AppImage).
    assert diagnostic_session._diagnostic_child_command(
        launcher="installed", source_root=source_root, appimage_active=True
    ) == [sys.executable, "-B", "-u", "-m", "keyrgb.tray"]


class _FakeDiagnostics:
    def to_dict(self) -> dict[str, object]:
        return {"ok": True}


def _fake_session_popen(command, **kwargs):
    class _FakeProcess:
        pass

    kwargs["stdout"].write("captured child output\n")
    kwargs["stdout"].flush()
    return _FakeProcess()


def test_run_diagnostic_session_creates_expected_files_and_prints_dir(tmp_path: Path, monkeypatch, capsys) -> None:
    session_root = tmp_path / "sessions"
    monkeypatch.setattr(diagnostic_session._runtime_capture, "discover_source_root", lambda: tmp_path)
    monkeypatch.setattr(diagnostic_session.subprocess, "Popen", _fake_session_popen)
    monkeypatch.setattr(diagnostic_session._runtime_capture, "_wait_with_signal_forwarding", lambda _process: 0)
    monkeypatch.setattr(dsev.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(diagnostics_pkg, "collect_diagnostics", lambda **_kwargs: _FakeDiagnostics())

    exit_code = diagnostic_session.run_diagnostic_session(output_dir_root=session_root)

    assert exit_code == 0
    session_dirs = [p for p in session_root.iterdir() if p.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]

    assert (session_dir / diagnostic_session.RUNTIME_LOG_NAME).is_file()
    assert (session_dir / dsev.DIAGNOSTICS_BEFORE_NAME).is_file()
    assert (session_dir / dsev.DIAGNOSTICS_AFTER_NAME).is_file()
    assert (session_dir / dsev.JOURNAL_USER_NAME).is_file()
    assert (session_dir / dsev.JOURNAL_KERNEL_NAME).is_file()

    before = json.loads((session_dir / dsev.DIAGNOSTICS_BEFORE_NAME).read_text(encoding="utf-8"))
    assert before == {"ok": True}

    captured = capsys.readouterr()
    assert f"Diagnostic session directory: {session_dir}" in captured.out
    # The user must be told to close any pre-existing tray before the child starts.
    assert "close any running keyrgb tray" in captured.out.lower()


def test_run_diagnostic_session_returns_child_status_when_collection_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    session_root = tmp_path / "sessions"
    monkeypatch.setattr(diagnostic_session._runtime_capture, "discover_source_root", lambda: tmp_path)
    monkeypatch.setattr(diagnostic_session.subprocess, "Popen", _fake_session_popen)
    monkeypatch.setattr(diagnostic_session._runtime_capture, "_wait_with_signal_forwarding", lambda _process: 0)
    # journalctl unavailable: collection must note and not change the exit code.
    monkeypatch.setattr(
        dsev.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("journalctl")),
    )
    monkeypatch.setattr(diagnostics_pkg, "collect_diagnostics", lambda **_kwargs: _FakeDiagnostics())

    assert diagnostic_session.run_diagnostic_session(output_dir_root=session_root) == 0

    session_dir = next(p for p in session_root.iterdir() if p.is_dir())
    note = (session_dir / dsev.JOURNAL_USER_NAME).read_text(encoding="utf-8")
    assert "journalctl is not available" in note


def test_run_diagnostic_session_source_without_checkout_fails_handled(tmp_path: Path, monkeypatch, capsys) -> None:
    session_root = tmp_path / "sessions"
    monkeypatch.setattr(diagnostic_session._runtime_capture, "discover_source_root", lambda: None)
    monkeypatch.setattr(diagnostic_session.subprocess, "Popen", _fake_session_popen)
    monkeypatch.setattr(diagnostic_session._runtime_capture, "_wait_with_signal_forwarding", lambda _process: 0)
    monkeypatch.setattr(dsev.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(diagnostics_pkg, "collect_diagnostics", lambda **_kwargs: _FakeDiagnostics())

    exit_code = diagnostic_session.run_diagnostic_session(launcher="source", output_dir_root=session_root)

    # Must be a handled RuntimeLogCaptureError, not an AssertionError, and the
    # session directory must still be reported.
    assert exit_code == 2
    session_dirs = [p for p in session_root.iterdir() if p.is_dir()]
    assert len(session_dirs) == 1
    captured = capsys.readouterr()
    assert f"Diagnostic session directory: {session_dirs[0]}" in captured.out
    assert "failed to launch" in captured.err


def test_run_diagnostic_session_uses_distinct_dirs_on_same_second(tmp_path: Path, monkeypatch) -> None:
    session_root = tmp_path / "sessions"

    class _FixedNow:
        def __init__(self, fixed: datetime) -> None:
            self._fixed = fixed

        def now(self, *_args: object, **_kwargs: object) -> datetime:
            return self._fixed

    monkeypatch.setattr(diagnostic_session._runtime_capture, "discover_source_root", lambda: tmp_path)
    monkeypatch.setattr(diagnostic_session.subprocess, "Popen", _fake_session_popen)
    monkeypatch.setattr(diagnostic_session._runtime_capture, "_wait_with_signal_forwarding", lambda _process: 0)
    monkeypatch.setattr(dsev.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(diagnostics_pkg, "collect_diagnostics", lambda **_kwargs: _FakeDiagnostics())
    monkeypatch.setattr(diagnostic_session, "datetime", _FixedNow(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)))

    first = diagnostic_session.run_diagnostic_session(output_dir_root=session_root)
    second = diagnostic_session.run_diagnostic_session(output_dir_root=session_root)

    assert first == 0 and second == 0
    dirs = sorted(p.name for p in session_root.iterdir() if p.is_dir())
    assert len(dirs) == 2
    assert dirs[0] != dirs[1]


def test_diagnostic_session_from_cli_dispatches_session(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def _fake_session(*, mode, launcher, output_dir_root, **_kwargs):
        calls.append(
            {
                "mode": mode,
                "launcher": launcher,
                "output_dir_root": output_dir_root,
            }
        )
        return 0

    monkeypatch.setattr(diagnostic_session, "run_diagnostic_session", _fake_session)

    assert diagnostic_session.diagnostic_session_from_cli(["--diagnostic-session"]) == 0
    assert calls == [{"mode": "full", "launcher": None, "output_dir_root": None}]

    assert (
        diagnostic_session.diagnostic_session_from_cli(
            [
                "--diagnostic-session",
                "--diagnostic-output-dir",
                "/tmp/diag-root",
                "--runtime-log-launcher",
                "source",
                "--diagnostic-mode",
                "debug",
            ]
        )
        == 0
    )
    assert calls[1] == {
        "mode": "debug",
        "launcher": "source",
        "output_dir_root": Path("/tmp/diag-root"),
    }


def test_diagnostic_session_from_cli_ignores_normal_launch() -> None:
    assert diagnostic_session.diagnostic_session_from_cli([]) is None
    # The older capture flag must not be claimed by the session parser.
    assert diagnostic_session.diagnostic_session_from_cli(["--capture-runtime-log"]) is None


def test_diagnostic_session_main_entrypoint_exits_with_child_status(monkeypatch) -> None:
    monkeypatch.setattr(diagnostic_session, "run_diagnostic_session", lambda **kwargs: 7)

    with pytest.raises(SystemExit) as exc_info:
        diagnostic_session.diagnostic_session_main([])

    assert exc_info.value.code == 7


def test_diagnostic_session_main_entrypoint_parses_output_dir(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_session(*, mode, launcher, output_dir_root, **_kwargs):
        captured["output_dir_root"] = output_dir_root
        return 0

    monkeypatch.setattr(diagnostic_session, "run_diagnostic_session", _fake_session)

    with pytest.raises(SystemExit) as exc_info:
        diagnostic_session.diagnostic_session_main(["--diagnostic-output-dir", "/tmp/diag-root"])

    assert exc_info.value.code == 0
    assert captured["output_dir_root"] == Path("/tmp/diag-root")


def test_collect_journal_log_writes_note_when_journalctl_missing(tmp_path: Path) -> None:
    target = tmp_path / "journal-user.log"
    orig_run = dsev.subprocess.run

    def _fake_run(*args, **kwargs):
        raise FileNotFoundError("journalctl")

    dsev.subprocess.run = _fake_run
    try:
        status = dsev._collect_journal_log(target, since="2026-01-01 00:00:00", cmd=["journalctl", "--user"])
    finally:
        dsev.subprocess.run = orig_run

    assert status is None
    assert "journalctl is not available" in target.read_text(encoding="utf-8")


def test_collect_journal_log_notes_nonzero_exit(tmp_path: Path) -> None:
    target = tmp_path / "journal-kernel.log"
    orig_run = dsev.subprocess.run

    def _fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1)

    dsev.subprocess.run = _fake_run
    try:
        status = dsev._collect_journal_log(target, since="2026-01-01 00:00:00", cmd=["journalctl", "-k"])
    finally:
        dsev.subprocess.run = orig_run

    assert status == 1
    assert "exited with status 1" in target.read_text(encoding="utf-8")
