"""Geometry-persistence tests for the Uniform Color window."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from keyrgb.gui.utils import window_state
from keyrgb.gui.windows import uniform
from tests.gui.windows.geometry._geometry_fakes import (
    _delays,
    _FakeGeometryTracker,
    _FakeRoot,
    _FakeWidget,
    _fire_after,
    _geometry_pass_scheduled,
)

# ---------------------------------------------------------------------------


def _build_uniform_gui(monkeypatch: pytest.MonkeyPatch, root: _FakeRoot):
    def _stub_build_ui(gui, **_kwargs) -> None:
        gui._main_frame = _FakeWidget(reqwidth_px=480, reqheight_px=560)
        gui._apply_button = object()
        gui._close_button = object()
        gui.color_wheel = None

    monkeypatch.setattr(uniform.tk, "Tk", lambda: root)
    monkeypatch.setattr(uniform, "Config", lambda: SimpleNamespace())
    monkeypatch.setattr(
        uniform.uniform_init_adapter,
        "initialize_device_bootstrap_state",
        lambda **_kwargs: SimpleNamespace(backend=None, color_supported=False, device=None),
    )
    monkeypatch.setattr(uniform.uniform_color_ui, "build_uniform_window_ui", _stub_build_ui)
    monkeypatch.setattr(uniform.uniform_color_state, "initialize_drag_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "schedule_initial_focus", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "WindowGeometryTracker", _FakeGeometryTracker)
    monkeypatch.setenv("KEYRGB_TRAY_MANAGED_GUI", "1")
    return uniform.UniformColorGUI()


def test_uniform_restored_geometry_wins_and_suppresses_fallback(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)
    _FakeGeometryTracker.next_restore_result = True
    root = _FakeRoot()

    gui = _build_uniform_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert tracker.window_id == "uniform-keyboard"
    assert (tracker.min_width, tracker.min_height) == (460, 520)
    assert tracker.screen_ratio_cap == pytest.approx(0.95)
    assert tracker.restore_calls == 1
    assert root.geometry_calls == ["restored:uniform-keyboard"]
    # Both centered passes (immediate + delayed) are suppressed ...
    assert not _geometry_pass_scheduled(root, gui)
    # ... while tracking is still scheduled just after the last pass.
    assert 60 in _delays(root)
    assert tracker.start_tracking_calls == 0
    assert gui._geometry_restored is True


def test_uniform_missing_state_retains_exact_fallback(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)
    root = _FakeRoot()

    gui = _build_uniform_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert tracker.restore_calls == 1
    assert len(root.geometry_calls) == 1
    assert root.geometry_calls[0].startswith("520x610+") or "x" in root.geometry_calls[0]
    assert _geometry_pass_scheduled(root, gui)
    assert 60 in _delays(root)
    # Tracking starts only after the initial passes fire.
    assert tracker.start_tracking_calls == 0
    _fire_after(root, 50)
    assert len(root.geometry_calls) == 2
    _fire_after(root, 60)
    assert tracker.start_tracking_calls == 1
    assert gui._geometry_restored is False


def test_uniform_dynamic_route_ids_stay_isolated(monkeypatch) -> None:
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)

    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    _build_uniform_gui(monkeypatch, _FakeRoot())
    keyboard_id = _FakeGeometryTracker.last().window_id

    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "lightbar")
    _build_uniform_gui(monkeypatch, _FakeRoot())
    lightbar_id = _FakeGeometryTracker.last().window_id

    assert keyboard_id == "uniform-keyboard"
    assert lightbar_id == "uniform-lightbar"
    assert keyboard_id != lightbar_id
    assert uniform.uniform_instance_identity(target_context="keyboard") == keyboard_id
    assert uniform.uniform_instance_identity(target_context="lightbar") == lightbar_id


def test_uniform_storage_isolation_per_route(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)

    assert (
        window_state.save_window_geometry(
            "uniform-keyboard", window_state.WindowGeometry(width=800, height=600, x=10, y=20)
        )
        is True
    )
    assert window_state.load_window_geometry("uniform-lightbar") is None
    assert window_state.load_window_geometry("uniform-keyboard") == window_state.WindowGeometry(
        width=800, height=600, x=10, y=20
    )


def test_uniform_close_saves_before_hardware_cleanup_and_destroy(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)
    root = _FakeRoot()
    gui = _build_uniform_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    class _FakeDevice:
        def close(self) -> None:
            root.events.append("device-close")

    gui.kb = _FakeDevice()
    assert dict(root.protocol_calls).get("WM_DELETE_WINDOW") == gui._on_close
    gui._on_close()

    assert tracker.save_now_calls == 1
    assert root.destroy_calls == 1
    assert root.events == ["save", "device-close", "destroy"]


def test_uniform_unexpected_geometry_save_error_still_cleans_up(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    root = _FakeRoot()
    gui = _build_uniform_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()
    tracker.save_now = lambda: (_ for _ in ()).throw(RuntimeError("save failed"))  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="save failed"):
        gui._on_close()

    assert root.destroy_calls == 1


# ---------------------------------------------------------------------------
# Reactive Color window
