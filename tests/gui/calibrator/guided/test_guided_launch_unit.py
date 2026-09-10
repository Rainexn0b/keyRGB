"""Unit coverage for the guided-session calibrator launcher."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from keyrgb.gui.calibrator import launch as calibrator_launch


def test_launch_guided_calibrator_argv_cwd_and_no_shell(tmp_path: Path, monkeypatch) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    class _FakePopen:
        def __init__(self, argv: object, **kwargs: object) -> None:
            captured["argv"] = argv
            captured["kwargs"] = kwargs

    monkeypatch.setattr(subprocess, "Popen", _FakePopen)

    calibrator_launch.launch_guided_calibrator(session_path)

    argv = captured["argv"]
    assert argv[:3] == [sys.executable, "-m", "keyrgb.gui.calibrator"]
    assert argv[3:] == ["--guided-session", str(session_path)]
    assert captured["kwargs"]["cwd"] == calibrator_launch.launcher_cwd_from(calibrator_launch.__file__)
    assert "shell" not in captured["kwargs"]


def test_launch_guided_preserves_interpreter_and_repo_root_convention(tmp_path: Path, monkeypatch) -> None:
    """Guided argv must match the standalone launcher plus the session flag."""

    calls: list[dict[str, object]] = []

    def _fake_popen(argv: object, **kwargs: object):
        calls.append({"argv": list(argv), "kwargs": dict(kwargs)})
        return object()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    calibrator_launch.launch_guided_calibrator(tmp_path / "s.json")
    calibrator_launch.launch_keymap_calibrator()

    assert len(calls) == 2
    guided, standalone = calls
    assert guided["argv"][:3] == standalone["argv"][:3] == [sys.executable, "-m", "keyrgb.gui.calibrator"]
    assert guided["argv"][3:] == ["--guided-session", str(tmp_path / "s.json")]
    assert standalone["argv"][3:] == []
    assert guided["kwargs"]["cwd"] == standalone["kwargs"]["cwd"]
    assert Path(str(guided["kwargs"]["cwd"])).exists()
