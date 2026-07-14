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
    monkeypatch.setenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", "1")

    gui_launch.launch_perkey_gui()

    assert len(launch_calls) == 1
    assert launch_calls[0]["module_name"] == "src.gui.perkey"
    assert launch_calls[0]["anchor"] == str(anchor)
    assert launch_calls[0]["env"]["KEYRGB_SIMULATE_SECONDARY_DEVICES"] == "1"


def test_launch_uniform_gui_inherits_secondary_simulation_flag(monkeypatch) -> None:
    launch_calls: list[dict[str, object]] = []

    def _fake_launch_module_subprocess(module_name: str, **kwargs):
        launch_calls.append({"module_name": module_name, **kwargs})
        return None

    monkeypatch.setenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", "1")
    monkeypatch.setattr(gui_launch, "launch_module_subprocess", _fake_launch_module_subprocess)

    gui_launch.launch_uniform_gui(target_context="logo", backend_name="ite8258-chassis-logo")

    assert len(launch_calls) == 1
    assert launch_calls[0]["module_name"] == "src.gui.windows.uniform"
    env = launch_calls[0]["env"]
    assert env["KEYRGB_SIMULATE_SECONDARY_DEVICES"] == "1"
    assert env["KEYRGB_UNIFORM_TARGET_CONTEXT"] == "logo"
    assert env["KEYRGB_UNIFORM_BACKEND"] == "ite8258-chassis-logo"


def test_launch_power_mode_settings_gui_uses_structural_repo_root_for_packaged_layout(
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

    gui_launch.launch_power_mode_settings_gui()

    assert launch_calls == [
        {
            "module_name": "src.gui.windows.power_mode",
            "anchor": str(anchor),
        }
    ]
