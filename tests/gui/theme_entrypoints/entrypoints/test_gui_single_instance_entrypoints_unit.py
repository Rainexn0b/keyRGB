"""UX-09: GUI entrypoints acquire the per-window single-instance lock first."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import keyrgb.gui as gui_pkg
from keyrgb.gui.calibrator import app as calibrator_app
from keyrgb.gui.perkey import launch as perkey_launch
from keyrgb.gui.settings import window as settings_window
from keyrgb.gui.windows import (
    power_mode as power_mode_window,
    reactive_color as reactive_color_window,
    support as support_window,
    uniform as uniform_window,
)


def _install_single_instance(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[tuple[str, ...]],
    *,
    duplicate: bool = False,
):
    def _acquire(identity: str) -> None:
        calls.append(("lock", identity))
        if duplicate:
            raise SystemExit(0)

    fake = SimpleNamespace(acquire_gui_instance_or_exit=_acquire)
    monkeypatch.setitem(sys.modules, "keyrgb.gui.single_instance", fake)
    monkeypatch.setattr(gui_pkg, "single_instance", fake, raising=False)
    return fake


def _install_gui_class(
    monkeypatch: pytest.MonkeyPatch,
    module,
    attr: str,
    calls: list[tuple[str, ...]],
):
    class _FakeGUI:
        def __init__(self, *args, **kwargs) -> None:
            calls.append(("construct", attr))

        def run(self) -> None:
            calls.append(("run", attr))

        def mainloop(self) -> None:
            calls.append(("run", attr))

    monkeypatch.setattr(module, attr, _FakeGUI)
    return _FakeGUI


def test_settings_main_acquires_lock_before_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls)
    _install_gui_class(monkeypatch, settings_window, "PowerSettingsGUI", calls)

    settings_window.main()

    assert calls == [("lock", "settings"), ("construct", "PowerSettingsGUI"), ("run", "PowerSettingsGUI")]


def test_settings_main_duplicate_exit_prevents_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls, duplicate=True)
    _install_gui_class(monkeypatch, settings_window, "PowerSettingsGUI", calls)

    with pytest.raises(SystemExit):
        settings_window.main()

    assert calls == [("lock", "settings")]


def test_reactive_color_main_acquires_lock_before_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls)
    _install_gui_class(monkeypatch, reactive_color_window, "ReactiveColorGUI", calls)

    reactive_color_window.main()

    assert calls == [("lock", "reactive-color"), ("construct", "ReactiveColorGUI"), ("run", "ReactiveColorGUI")]


def test_reactive_color_main_duplicate_exit_prevents_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls, duplicate=True)
    _install_gui_class(monkeypatch, reactive_color_window, "ReactiveColorGUI", calls)

    with pytest.raises(SystemExit):
        reactive_color_window.main()

    assert calls == [("lock", "reactive-color")]


def test_reactive_color_main_preserves_keyboard_interrupt_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls)

    class _InterruptingGUI:
        def run(self) -> None:
            calls.append(("run", "ReactiveColorGUI"))
            raise KeyboardInterrupt

    monkeypatch.setattr(reactive_color_window, "ReactiveColorGUI", _InterruptingGUI)

    reactive_color_window.main()

    assert calls[0] == ("lock", "reactive-color")
    assert ("run", "ReactiveColorGUI") in calls


def test_power_mode_main_acquires_lock_before_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls)
    _install_gui_class(monkeypatch, power_mode_window, "PowerModeSettingsGUI", calls)

    power_mode_window.main()

    assert calls == [("lock", "power-mode"), ("construct", "PowerModeSettingsGUI"), ("run", "PowerModeSettingsGUI")]


def test_power_mode_main_duplicate_exit_prevents_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls, duplicate=True)
    _install_gui_class(monkeypatch, power_mode_window, "PowerModeSettingsGUI", calls)

    with pytest.raises(SystemExit):
        power_mode_window.main()

    assert calls == [("lock", "power-mode")]


def test_support_main_acquires_lock_before_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls)
    _install_gui_class(monkeypatch, support_window, "SupportToolsGUI", calls)

    support_window.main()

    assert calls == [("lock", "support"), ("construct", "SupportToolsGUI"), ("run", "SupportToolsGUI")]


def test_support_main_duplicate_exit_prevents_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls, duplicate=True)
    _install_gui_class(monkeypatch, support_window, "SupportToolsGUI", calls)

    with pytest.raises(SystemExit):
        support_window.main()

    assert calls == [("lock", "support")]


def test_perkey_main_acquires_lock_before_editor_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls)

    from keyrgb.gui.perkey import editor as perkey_editor

    class _FakeEditor:
        def __init__(self, *args, **kwargs) -> None:
            calls.append(("construct", "PerKeyEditor"))

        def run(self) -> None:
            calls.append(("run", "PerKeyEditor"))

    monkeypatch.setattr(perkey_editor, "PerKeyEditor", _FakeEditor)

    perkey_launch.main()

    assert calls == [("lock", "perkey"), ("construct", "PerKeyEditor"), ("run", "PerKeyEditor")]


def test_perkey_main_duplicate_exit_prevents_editor_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls, duplicate=True)

    from keyrgb.gui.perkey import editor as perkey_editor

    class _FakeEditor:
        def __init__(self, *args, **kwargs) -> None:
            calls.append(("construct", "PerKeyEditor"))

        def run(self) -> None:
            calls.append(("run", "PerKeyEditor"))

    monkeypatch.setattr(perkey_editor, "PerKeyEditor", _FakeEditor)

    with pytest.raises(SystemExit):
        perkey_launch.main()

    assert calls == [("lock", "perkey")]


def test_calibrator_main_acquires_lock_before_window_construction(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls)

    config_dir = tmp_path / "keyrgb-config"
    fake_config = SimpleNamespace(CONFIG_DIR=config_dir)

    class _FakeConfigDir:
        def mkdir(self, *args, **kwargs) -> None:
            calls.append(("mkdir", "config-dir"))
            config_dir.mkdir(*args, **kwargs)

    fake_config.CONFIG_DIR = _FakeConfigDir()
    monkeypatch.setattr(calibrator_app, "Config", fake_config)
    _install_gui_class(monkeypatch, calibrator_app, "KeymapCalibrator", calls)

    calibrator_app.main()

    assert calls[0] == ("lock", "calibrator")
    assert ("construct", "KeymapCalibrator") in calls
    assert ("run", "KeymapCalibrator") in calls
    assert calls.index(("lock", "calibrator")) < calls.index(("construct", "KeymapCalibrator"))


def test_calibrator_main_duplicate_exit_prevents_window_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls, duplicate=True)
    _install_gui_class(monkeypatch, calibrator_app, "KeymapCalibrator", calls)

    with pytest.raises(SystemExit):
        calibrator_app.main()

    assert calls == [("lock", "calibrator")]


@pytest.mark.parametrize(
    ("target_context", "requested_backend", "expected"),
    [
        ("keyboard", "", "uniform-keyboard"),
        ("keyboard", None, "uniform-keyboard"),
        ("", "", "uniform-keyboard"),
        ("   ", "", "uniform-keyboard"),
        ("KEYBOARD", "", "uniform-keyboard"),
        ("lightbar", "", "uniform-lightbar"),
        ("mouse", "", "uniform-mouse"),
        ("logo", "", "uniform-ite8258-chassis-logo"),
        ("neon", "", "uniform-ite8258-chassis-neon"),
        ("vent", "", "uniform-ite8258-chassis-vent"),
        ("lightbar:extra", "", "uniform-lightbar"),
        # Explicit backend wins over the target context.
        ("keyboard", "ite8233_none_chassis_lightbar_clevo", "uniform-lightbar"),
        ("lightbar", "sysfs-mouse", "uniform-mouse"),
        ("keyboard", "ite8258-chassis-logo", "uniform-ite8258-chassis-logo"),
        ("keyboard", "ite8258-chassis-neon", "uniform-ite8258-chassis-neon"),
        ("keyboard", "ite8258-chassis-vent", "uniform-ite8258-chassis-vent"),
    ],
)
def test_uniform_instance_identity_raw_context_backend_priority(
    target_context: str, requested_backend: str | None, expected: str
) -> None:
    assert (
        uniform_window.uniform_instance_identity(
            target_context=target_context,
            requested_backend=requested_backend,
        )
        == expected
    )


def test_uniform_instance_identity_reads_tray_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "logo")
    monkeypatch.setenv("KEYRGB_UNIFORM_BACKEND", "ite8258-chassis-logo")
    assert uniform_window.uniform_instance_identity() == "uniform-ite8258-chassis-logo"


def test_uniform_instance_identity_defaults_to_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_UNIFORM_TARGET_CONTEXT", raising=False)
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)
    assert uniform_window.uniform_instance_identity() == "uniform-keyboard"


def test_uniform_main_acquires_canonical_lock_before_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls)
    _install_gui_class(monkeypatch, uniform_window, "UniformColorGUI", calls)
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "logo")
    monkeypatch.setenv("KEYRGB_UNIFORM_BACKEND", "ite8258-chassis-logo")

    uniform_window.main()

    assert calls == [
        ("lock", "uniform-ite8258-chassis-logo"),
        ("construct", "UniformColorGUI"),
        ("run", "UniformColorGUI"),
    ]


def test_uniform_main_keyboard_context_uses_keyboard_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls)
    _install_gui_class(monkeypatch, uniform_window, "UniformColorGUI", calls)
    monkeypatch.delenv("KEYRGB_UNIFORM_TARGET_CONTEXT", raising=False)
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)

    uniform_window.main()

    assert calls[0] == ("lock", "uniform-keyboard")


def test_uniform_main_duplicate_exit_prevents_gui_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    _install_single_instance(monkeypatch, calls, duplicate=True)
    _install_gui_class(monkeypatch, uniform_window, "UniformColorGUI", calls)
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "mouse")

    with pytest.raises(SystemExit):
        uniform_window.main()

    assert calls == [("lock", "uniform-mouse")]
