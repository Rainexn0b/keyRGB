from __future__ import annotations

from pathlib import Path

from src.tray.ui import gui_launch


def test_launch_perkey_gui_uses_structural_repo_root_for_packaged_layout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "src" / "tray" / "ui" / "gui_launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "src").mkdir(exist_ok=True)

    popen_calls: list[dict[str, object]] = []

    def _fake_popen(args, **kwargs):
        popen_calls.append({"args": list(args), **kwargs})
        return None

    monkeypatch.setattr(gui_launch, "__file__", str(anchor))
    monkeypatch.setattr(gui_launch.subprocess, "Popen", _fake_popen)

    gui_launch.launch_perkey_gui()

    assert popen_calls == [
        {
            "args": [gui_launch.sys.executable, "-B", "-m", "src.gui.perkey"],
            "cwd": str(runtime_root),
        }
    ]
