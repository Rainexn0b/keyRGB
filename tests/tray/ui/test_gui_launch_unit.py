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

    launch_calls: list[dict[str, object]] = []

    def _fake_launch_module_subprocess(module_name: str, **kwargs):
        launch_calls.append({"module_name": module_name, **kwargs})
        return None

    monkeypatch.setattr(gui_launch, "__file__", str(anchor))
    monkeypatch.setattr(gui_launch, "launch_module_subprocess", _fake_launch_module_subprocess)

    gui_launch.launch_perkey_gui()

    assert launch_calls == [
        {
            "module_name": "src.gui.perkey",
            "anchor": str(anchor),
        }
    ]
