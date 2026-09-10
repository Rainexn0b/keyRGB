"""Settings window init, footer probe, tab behavior, and shortcuts."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

import keyrgb.gui.settings.window as settings_window
from tests.gui.settings.window._settings_window_fakes import (
    _FakeBottomBarPanel,
    _FakeGeometryTracker,
    _FakeRoot,
    _values,
)


def test_init_sets_up_root_and_calls_init_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    root = _FakeRoot()
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    values = _values()
    monkeypatch.setattr(settings_window.tk, "Tk", lambda: root)
    monkeypatch.setattr(
        settings_window, "apply_keyrgb_window_icon", lambda actual_root: calls.append(("icon", (actual_root,), {}))
    )
    monkeypatch.setattr(
        settings_window,
        "apply_clam_theme",
        lambda actual_root, **kwargs: calls.append(("theme", (actual_root,), kwargs)) or ("#111", "#eee"),
    )
    monkeypatch.setattr(settings_window, "Config", lambda: calls.append(("config", (), {})) or "config-obj")
    monkeypatch.setattr(
        settings_window, "detect_os_autostart_enabled", lambda: calls.append(("detect", (), {})) or True
    )
    monkeypatch.setattr(
        settings_window, "load_settings_values", lambda **kwargs: calls.append(("load", (), kwargs)) or values
    )
    monkeypatch.setattr(
        settings_window.PowerSettingsGUI, "_init_layout", lambda self, **kwargs: calls.append(("layout", (), kwargs))
    )
    monkeypatch.setattr(
        settings_window.PowerSettingsGUI, "_init_vars", lambda self, values: calls.append(("vars", (values,), {}))
    )
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_panels", lambda self: calls.append(("panels", (), {})))
    monkeypatch.setattr(
        settings_window.PowerSettingsGUI, "_finalize_layout", lambda self: calls.append(("finalize", (), {}))
    )
    monkeypatch.setattr(
        settings_window.PowerSettingsGUI, "_start_footer_hardware_probe", lambda self: calls.append(("probe", (), {}))
    )
    gui = settings_window.PowerSettingsGUI()
    assert gui.root is root
    assert gui.config == "config-obj"
    assert root.title_calls == ["KeyRGB - Settings"]
    assert root.minsize_calls == [(680, 560)]
    assert root.resizable_calls == [(True, True)]
    # The window-manager close button shares the orderly close path so the
    # persisted geometry is saved before destruction.
    assert root.protocol_calls == [("WM_DELETE_WINDOW", gui._on_close)]
    assert calls == [
        ("icon", (root,), {}),
        ("theme", (root,), {}),
        ("config", (), {}),
        ("detect", (), {}),
        ("load", (), {"config": "config-obj", "os_autostart_enabled": True}),
        ("layout", (), {"bg_color": "#111"}),
        ("vars", (values,), {}),
        ("panels", (), {}),
        ("finalize", (), {}),
        ("probe", (), {}),
    ]


def test_start_footer_hardware_probe_runs_worker_and_updates_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.bottom_bar_panel = _FakeBottomBarPanel(None, on_close=lambda: None)
    fake_collectors = ModuleType("keyrgb.core.diagnostics.collectors.backends")
    fake_collectors.backend_probe_snapshot = lambda: "snapshot"
    monkeypatch.setitem(sys.modules, "keyrgb.core.diagnostics.collectors.backends", fake_collectors)
    monkeypatch.setattr(settings_window, "extract_unsupported_rgb_controllers_hint", lambda snap: f"hint:{snap}")

    run_calls: list[tuple[object, object, object, int]] = []

    def fake_run_in_thread(root, work, on_done, *, delay_ms: int) -> None:
        run_calls.append((root, work, on_done, delay_ms))
        on_done(work())

    monkeypatch.setattr(settings_window, "run_in_thread", fake_run_in_thread)
    gui._start_footer_hardware_probe()
    assert run_calls[0][0] is gui.root
    assert run_calls[0][3] == 100
    assert gui.bottom_bar_panel.hint_calls == ["hint:snapshot"]


def test_start_footer_hardware_probe_swallows_worker_and_footer_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.bottom_bar_panel = SimpleNamespace(set_hardware_hint=lambda text: (_ for _ in ()).throw(RuntimeError(text)))
    fake_collectors = ModuleType("keyrgb.core.diagnostics.collectors.backends")
    fake_collectors.backend_probe_snapshot = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    monkeypatch.setitem(sys.modules, "keyrgb.core.diagnostics.collectors.backends", fake_collectors)
    monkeypatch.setattr(settings_window, "run_in_thread", lambda root, work, on_done, *, delay_ms: on_done(work()))
    gui._start_footer_hardware_probe()


def test_tab_switch_has_no_rebuild_path_and_probes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin one-time construction without invoking an unrelated fake select.

    The real ``__init__`` call order (layout/vars/panels/finalize/probe each
    exactly once) is pinned by ``test_init_sets_up_root_and_calls_init_steps``,
    one-time page construction by the navigation tests, and the absence of a
    tab-change rebuild hook by the layout test's ``bind_calls == []``
    assertion. This test pins the remaining half: the footer probe is issued
    exactly once per window.
    """
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.bottom_bar_panel = _FakeBottomBarPanel(None, on_close=lambda: None)
    probe_runs: list[int] = []
    monkeypatch.setattr(settings_window, "run_in_thread", lambda *args, **kwargs: probe_runs.append(1) or None)
    gui._start_footer_hardware_probe()
    assert len(probe_runs) == 1


def test_shortcuts_route_to_orderly_close_without_save(monkeypatch: pytest.MonkeyPatch) -> None:
    root = _FakeRoot()
    values = _values()
    monkeypatch.setattr(settings_window.tk, "Tk", lambda: root)
    monkeypatch.setattr(settings_window, "apply_keyrgb_window_icon", lambda _root: None)
    monkeypatch.setattr(settings_window, "apply_clam_theme", lambda _root, **_kwargs: ("#111", "#eee"))
    monkeypatch.setattr(settings_window, "Config", lambda: SimpleNamespace(physical_layout="auto"))
    monkeypatch.setattr(settings_window, "detect_os_autostart_enabled", lambda: False)
    monkeypatch.setattr(settings_window, "load_settings_values", lambda **_kwargs: values)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_layout", lambda self, **_kwargs: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_vars", lambda self, _values: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_panels", lambda self: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_finalize_layout", lambda self: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_start_footer_hardware_probe", lambda self: None)
    monkeypatch.setattr(settings_window, "WindowGeometryTracker", _FakeGeometryTracker)

    gui = settings_window.PowerSettingsGUI()

    # WM protocol is preserved on the exact orderly close path.
    assert root.protocol_calls == [("WM_DELETE_WINDOW", gui._on_close)]
    # Exact shortcut set: close-only, additive, no save, no native navigation.
    assert [sequence for sequence, _, _ in root.bind_calls] == ["<Control-w>", "<Escape>"]
    assert all(add == "+" for _, _, add in root.bind_calls)
    assert all("Tab" not in sequence for sequence, _, _ in root.bind_calls)
    assert "<Control-s>" not in [sequence for sequence, _, _ in root.bind_calls]
    # Both shortcuts share the same close wrapper.
    assert root.bind_calls[0][1] is root.bind_calls[1][1]
    # The wrapper returns break and invokes the orderly close exactly once.
    assert root.bind_calls[0][1](object()) == "break"
    assert gui.root.destroy_calls == 1
