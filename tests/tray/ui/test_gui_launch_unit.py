from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from keyrgb.core.backends.base import BackendCapabilities
from keyrgb.tray.ui import gui_launch


def test_launch_perkey_gui_uses_structural_repo_root_for_packaged_layout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "keyrgb" / "tray" / "ui" / "gui_launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "keyrgb").mkdir(exist_ok=True)

    launch_calls: list[dict[str, object]] = []

    def _fake_launch_module_subprocess(module_name: str, **kwargs):
        launch_calls.append({"module_name": module_name, **kwargs})

    monkeypatch.setattr(gui_launch, "__file__", str(anchor))
    monkeypatch.setattr(gui_launch, "launch_module_subprocess", _fake_launch_module_subprocess)
    monkeypatch.setenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", "1")

    gui_launch.launch_perkey_gui()

    assert len(launch_calls) == 1
    assert launch_calls[0]["module_name"] == "keyrgb.gui.perkey"
    assert launch_calls[0]["anchor"] == str(anchor)
    assert launch_calls[0]["env"]["KEYRGB_SIMULATE_SECONDARY_DEVICES"] == "1"
    assert launch_calls[0]["env"]["KEYRGB_TRAY_MANAGED_GUI"] == "1"
    assert launch_calls[0]["env"]["KEYRGB_TRAY_PID"]


def test_launch_uniform_gui_inherits_secondary_simulation_flag(monkeypatch) -> None:
    launch_calls: list[dict[str, object]] = []

    def _fake_launch_module_subprocess(module_name: str, **kwargs):
        launch_calls.append({"module_name": module_name, **kwargs})

    monkeypatch.setenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", "1")
    monkeypatch.setattr(gui_launch, "launch_module_subprocess", _fake_launch_module_subprocess)

    gui_launch.launch_uniform_gui(target_context="logo", backend_name="ite8258-chassis-logo")

    assert len(launch_calls) == 1
    assert launch_calls[0]["module_name"] == "keyrgb.gui.windows.uniform"
    env = launch_calls[0]["env"]
    assert env["KEYRGB_SIMULATE_SECONDARY_DEVICES"] == "1"
    assert env["KEYRGB_UNIFORM_TARGET_CONTEXT"] == "logo"
    assert env["KEYRGB_UNIFORM_BACKEND"] == "ite8258-chassis-logo"
    assert env["KEYRGB_TRAY_MANAGED_GUI"] == "1"
    assert env["KEYRGB_TRAY_PID"]


def test_launch_power_mode_settings_gui_uses_structural_repo_root_for_packaged_layout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "keyrgb" / "tray" / "ui" / "gui_launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "keyrgb").mkdir(exist_ok=True)

    launch_calls: list[dict[str, object]] = []

    def _fake_launch_module_subprocess(module_name: str, **kwargs):
        launch_calls.append({"module_name": module_name, **kwargs})

    monkeypatch.setattr(gui_launch, "__file__", str(anchor))
    monkeypatch.setattr(gui_launch, "launch_module_subprocess", _fake_launch_module_subprocess)

    gui_launch.launch_power_mode_settings_gui()

    assert launch_calls == [
        {
            "module_name": "keyrgb.gui.windows.power_mode",
            "anchor": str(anchor),
        }
    ]


def test_launch_perkey_gui_no_args_omits_preflight_snapshot(monkeypatch) -> None:
    launch_calls: list[dict[str, object]] = []

    def _fake_launch_module_subprocess(module_name: str, **kwargs):
        launch_calls.append({"module_name": module_name, **kwargs})

    monkeypatch.setattr(gui_launch, "launch_module_subprocess", _fake_launch_module_subprocess)
    monkeypatch.delenv(gui_launch.PERKEY_PREFLIGHT_ENV_VAR, raising=False)

    # No-argument compatibility for existing callers/tests.
    gui_launch.launch_perkey_gui()

    assert len(launch_calls) == 1
    assert launch_calls[0]["module_name"] == "keyrgb.gui.perkey"
    env = launch_calls[0]["env"]
    assert env["KEYRGB_TRAY_MANAGED_GUI"] == "1"
    assert gui_launch.PERKEY_PREFLIGHT_ENV_VAR not in env


def test_launch_perkey_gui_serializes_cached_snapshot_without_probing(monkeypatch) -> None:
    launch_calls: list[dict[str, object]] = []

    def _fake_launch_module_subprocess(module_name: str, **kwargs):
        launch_calls.append({"module_name": module_name, **kwargs})

    monkeypatch.setattr(gui_launch, "launch_module_subprocess", _fake_launch_module_subprocess)

    caps = BackendCapabilities(
        brightness=True,
        per_key=True,
        color=True,
        hardware_effects=False,
        palette=False,
    )
    gui_launch.launch_perkey_gui(backend_caps=caps, backend_name="ite8291r3_perkey", dimensions=(6, 18))

    assert len(launch_calls) == 1
    payload = json.loads(launch_calls[0]["env"][gui_launch.PERKEY_PREFLIGHT_ENV_VAR])
    assert payload == {
        "brightness": True,
        "per_key": True,
        "color": True,
        "hardware_effects": False,
        "palette": False,
        "backend_name": "ite8291r3_perkey",
        "dimensions": [6, 18],
    }
    assert all(type(payload[key]) is bool for key in ("brightness", "per_key", "color", "hardware_effects", "palette"))


def test_launch_perkey_gui_normalizes_partial_caps_and_omits_invalid_dimensions(monkeypatch) -> None:
    launch_calls: list[dict[str, object]] = []

    def _fake_launch_module_subprocess(module_name: str, **kwargs):
        launch_calls.append({"module_name": module_name, **kwargs})

    monkeypatch.setattr(gui_launch, "launch_module_subprocess", _fake_launch_module_subprocess)

    gui_launch.launch_perkey_gui(
        backend_caps=SimpleNamespace(per_key=True),
        backend_name="  ",
        dimensions="6x18",
    )

    payload = json.loads(launch_calls[0]["env"][gui_launch.PERKEY_PREFLIGHT_ENV_VAR])
    assert payload["per_key"] is True
    assert payload["brightness"] is False
    assert payload["color"] is False
    assert payload["backend_name"] is None
    assert payload["dimensions"] is None


def test_perkey_preflight_snapshot_from_tray_reads_cached_backend_only() -> None:
    caps = SimpleNamespace(per_key=True, color=True)
    backend = SimpleNamespace(name="ite8291r3_perkey", dimensions=lambda: (6, 18))
    tray = SimpleNamespace(backend_caps=caps, backend=backend)

    snapshot_caps, snapshot_name, snapshot_dimensions = gui_launch.perkey_preflight_snapshot_from_tray(tray)

    assert snapshot_caps is caps
    assert snapshot_name == "ite8291r3_perkey"
    assert snapshot_dimensions == (6, 18)


def test_perkey_preflight_snapshot_from_tray_omits_failing_dimensions() -> None:
    def _raise_dimensions():
        raise OSError("device busy")

    tray = SimpleNamespace(backend_caps=None, backend=SimpleNamespace(name="x", dimensions=_raise_dimensions))

    snapshot_caps, snapshot_name, snapshot_dimensions = gui_launch.perkey_preflight_snapshot_from_tray(tray)

    assert snapshot_caps is None
    assert snapshot_name == "x"
    assert snapshot_dimensions is None
