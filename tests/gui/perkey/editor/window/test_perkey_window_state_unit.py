"""UX-06 window-geometry integration for the per-key editor.

Covers restore-vs-fallback in ``editor_support.bootstrap.initialize_editor``,
tracker wiring (identity, computed minimum, screen cap), tracking order, and
the final synchronous save through ``PerKeyEditor._on_close``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from keyrgb.gui.perkey import editor as editor_module
from keyrgb.gui.perkey.editor_support import bootstrap


class _Var:
    def __init__(self, value: object = "") -> None:
        self.value = value

    def get(self) -> object:
        return self.value

    def set(self, value: object) -> None:
        self.value = value


class _Root:
    """Tracker-capable fake root recording geometry call order."""

    def __init__(self, *, screen_w: int = 1920, screen_h: int = 1080) -> None:
        self._screen_w = int(screen_w)
        self._screen_h = int(screen_h)
        self.calls: list[tuple[object, ...]] = []
        self.protocols: dict[str, object] = {}
        self.after_calls: list[tuple[int, object]] = []

    def title(self, text: str) -> None:
        self.calls.append(("title", text))

    def update_idletasks(self) -> None:
        self.calls.append(("update_idletasks",))

    def protocol(self, name: str, func: object) -> None:
        self.protocols[name] = func

    def bind(self, sequence: str, func: object, add: object = None) -> None:
        self.calls.append(("bind", sequence, add))

    def after(self, delay_ms: int, callback: object) -> str:
        self.after_calls.append((delay_ms, callback))
        self.calls.append(("after", delay_ms))
        return "after1"

    def after_cancel(self, after_id: object) -> None:
        self.calls.append(("after_cancel", after_id))

    def winfo_screenwidth(self) -> int:
        return self._screen_w

    def winfo_screenheight(self) -> int:
        return self._screen_h

    def winfo_width(self) -> int:
        return 800

    def winfo_height(self) -> int:
        return 600

    def winfo_x(self) -> int:
        return 10

    def winfo_y(self) -> int:
        return 20

    def winfo_reqwidth(self) -> int:
        return 900

    def winfo_reqheight(self) -> int:
        return 700

    def geometry(self, value: str) -> None:
        self.calls.append(("geometry", str(value)))

    def minsize(self, width: int, height: int) -> None:
        self.calls.append(("minsize", int(width), int(height)))


class _Tk:
    def __init__(self, root: _Root) -> None:
        self.root = root

    def Tk(self) -> _Root:
        return self.root

    def StringVar(self, value: object = "") -> _Var:
        return _Var(value)

    def BooleanVar(self, value: object = False) -> _Var:
        return _Var(value)

    def DoubleVar(self, value: object = 0.0) -> _Var:
        return _Var(value)


class _Config:
    def __init__(self) -> None:
        self.physical_layout = "ansi"
        self.layout_legend_pack = "auto"
        self.color = (10, 20, 30)
        self.ac_perkey_profile_name = ""
        self.battery_perkey_profile_name = ""


class _FakeTracker:
    """Stand-in for WindowGeometryTracker with a scripted restore result."""

    last_instance: _FakeTracker | None = None

    def __init__(
        self,
        root: object,
        window_id: str,
        min_width: int,
        min_height: int,
        screen_ratio_cap: float = 0.95,
        debounce_ms: int = 500,
    ) -> None:
        self.root = root
        self.window_id = window_id
        self.min_width = int(min_width)
        self.min_height = int(min_height)
        self.screen_ratio_cap = float(screen_ratio_cap)
        self.debounce_ms = int(debounce_ms)
        self.restore_result = False
        self.restore_calls = 0
        self.start_tracking_calls = 0
        self.save_now_calls = 0
        _FakeTracker.last_instance = self

    def restore(self) -> bool:
        self.restore_calls += 1
        if self.restore_result:
            self.root.geometry("900x700+33+44")  # type: ignore[union-attr]
        return self.restore_result

    def start_tracking(self) -> None:
        self.start_tracking_calls += 1

    def save_now(self) -> bool:
        self.save_now_calls += 1
        return True


def _run_initialize_editor(
    monkeypatch: pytest.MonkeyPatch,
    root: _Root,
    *,
    restore_result: bool,
) -> tuple[SimpleNamespace, MagicMock, MagicMock, MagicMock]:
    monkeypatch.setattr(bootstrap.dirty_state, "mark_saved", lambda _editor: None)

    def _tracker_factory(
        root_arg: object,
        window_id: str,
        min_width: int,
        min_height: int,
        screen_ratio_cap: float = 0.95,
        debounce_ms: int = 500,
    ) -> _FakeTracker:
        tracker = _FakeTracker(root_arg, window_id, min_width, min_height, screen_ratio_cap, debounce_ms)
        tracker.restore_result = restore_result
        return tracker

    monkeypatch.setattr(bootstrap, "WindowGeometryTracker", _tracker_factory)

    app = SimpleNamespace(
        _detect_lightbar_device=lambda: False,
        _load_keymap=lambda: {"esc": ((0, 0),)},
        _load_layout_tweaks=dict,
        _load_per_key_layout_tweaks=dict,
        _load_layout_slot_overrides=dict,
        _get_visible_layout_keys=lambda: [
            SimpleNamespace(key_id="esc", slot_id="slot_esc"),
        ],
        select_slot_id=MagicMock(),
        _on_close=MagicMock(),
        _save_profile=MagicMock(),
        canvas=SimpleNamespace(redraw=MagicMock()),
    )
    profiles = SimpleNamespace(
        get_active_profile=lambda: "Default",
        load_lightbar_overlay=lambda _n: {},
        load_backdrop_mode=lambda _n: "none",
        load_backdrop_transparency=lambda _n: 0.0,
    )
    apply_geometry = MagicMock()
    fit_geometry = MagicMock()
    build_ui = MagicMock()
    bootstrap.initialize_editor(
        app,
        tk=_Tk(root),
        config_cls=_Config,
        profiles=profiles,
        apply_keyrgb_window_icon=lambda _root: None,
        apply_perkey_editor_geometry=apply_geometry,
        compute_perkey_editor_min_content_size=lambda **_kwargs: (800, 600),
        fit_perkey_editor_geometry_to_content=fit_geometry,
        apply_clam_theme=lambda _root, **_kwargs: ("#111", "#eee"),
        normalize_layout_legend_pack_fn=lambda layout, _pack: layout,
        initial_last_non_black_color=lambda _color: (1, 2, 3),
        load_profile_colors=lambda **_kwargs: {},
        per_key_commit_pipeline_cls=lambda **_kwargs: object(),
        get_keyboard=lambda: None,
        build_ui_fn=build_ui,
        set_status=lambda _editor, _msg: None,
        no_keymap_found_initial=lambda: "no-map",
        num_rows=6,
        num_cols=21,
    )
    return app, apply_geometry, fit_geometry, build_ui


def test_tracker_wired_with_perkey_identity_computed_minimum_and_screen_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _Root()
    _FakeTracker.last_instance = None
    app, _apply_geometry, _fit_geometry, _build_ui = _run_initialize_editor(monkeypatch, root, restore_result=False)

    tracker = _FakeTracker.last_instance
    assert tracker is not None
    assert tracker.root is root
    assert tracker.window_id == "perkey"
    assert (tracker.min_width, tracker.min_height) == (800, 600)
    assert tracker.screen_ratio_cap == pytest.approx(0.92)
    assert root.protocols["WM_DELETE_WINDOW"] == app._on_close


def test_restore_true_suppresses_apply_and_fits_but_keeps_minsize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _Root()
    app, apply_geometry, fit_geometry, _build_ui = _run_initialize_editor(monkeypatch, root, restore_result=True)

    # Restored geometry must not be overwritten by centering/fitting passes.
    apply_geometry.assert_not_called()
    fit_geometry.assert_not_called()
    assert [delay for delay, _cb in root.after_calls] == [60]

    geometry_calls = [call for call in root.calls if call[0] == "geometry"]
    assert geometry_calls == [("geometry", "900x700+33+44")]
    # Resize floor grows to the post-theme requested content without moving.
    assert ("minsize", 900, 700) in root.calls

    tracker = _FakeTracker.last_instance
    assert tracker is not None
    assert tracker.restore_calls == 1
    assert tracker.start_tracking_calls == 0
    root.after_calls[0][1]()
    assert tracker.start_tracking_calls == 1
    assert app._window_geometry_tracker is tracker


def test_restore_false_preserves_exact_fallback_then_starts_tracking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _Root()
    app, apply_geometry, fit_geometry, _build_ui = _run_initialize_editor(monkeypatch, root, restore_result=False)

    apply_geometry.assert_called_once()
    assert fit_geometry.call_count == 1
    assert [delay for delay, _cb in root.after_calls] == [50, 60]

    # Tracking starts after all startup geometry passes.
    tracker = _FakeTracker.last_instance
    assert tracker is not None
    assert tracker.start_tracking_calls == 0
    by_delay = dict(root.after_calls)
    by_delay[50]()
    assert fit_geometry.call_count == 2
    assert tracker.start_tracking_calls == 0
    by_delay[60]()
    assert tracker.start_tracking_calls == 1
    assert app._window_geometry_tracker is tracker


def test_on_close_saves_geometry_before_destroy(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    tracker = _FakeTracker(_Root(), "perkey", 800, 600)
    original_save_now = tracker.save_now

    def _save_now() -> bool:
        order.append("save_now")
        return original_save_now()

    tracker.save_now = _save_now  # type: ignore[method-assign]
    editor = SimpleNamespace(
        profile_name="Default",
        _profile_name_var=SimpleNamespace(get=lambda: "Default", set=lambda _v: None),
        _save_profile=lambda: None,
        kb=None,
        root=SimpleNamespace(destroy=lambda: order.append("destroy")),
        _window_geometry_tracker=tracker,
    )
    vars(editor)["_profile_name_var"] = editor._profile_name_var
    monkeypatch.setattr(editor_module.dirty_state, "confirm_destructive_action", lambda *_a, **_k: True)
    monkeypatch.setattr(editor_module.hardware, "release_hardware_control", lambda: order.append("release"))

    editor_module.PerKeyEditor._on_close(editor)

    assert order == ["save_now", "release", "destroy"]
    assert tracker.save_now_calls == 1


def test_on_close_without_tracker_still_destroys(monkeypatch: pytest.MonkeyPatch) -> None:
    destroyed: list[str] = []
    editor = SimpleNamespace(
        profile_name="Default",
        _profile_name_var=SimpleNamespace(get=lambda: "Default", set=lambda _v: None),
        _save_profile=lambda: None,
        kb=None,
        root=SimpleNamespace(destroy=lambda: destroyed.append("destroy")),
    )
    vars(editor)["_profile_name_var"] = editor._profile_name_var
    monkeypatch.setattr(editor_module.dirty_state, "confirm_destructive_action", lambda *_a, **_k: True)
    monkeypatch.setattr(editor_module.hardware, "release_hardware_control", lambda: None)

    editor_module.PerKeyEditor._on_close(editor)

    assert destroyed == ["destroy"]


def test_unexpected_geometry_save_error_still_releases_and_destroys(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    tracker = SimpleNamespace(save_now=lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    editor = SimpleNamespace(
        profile_name="Default",
        _profile_name_var=SimpleNamespace(get=lambda: "Default", set=lambda _v: None),
        _save_profile=lambda: None,
        kb=None,
        root=SimpleNamespace(destroy=lambda: order.append("destroy")),
        _window_geometry_tracker=tracker,
    )
    monkeypatch.setattr(editor_module.dirty_state, "confirm_destructive_action", lambda *_a, **_k: True)
    monkeypatch.setattr(editor_module.hardware, "release_hardware_control", lambda: order.append("release"))

    with pytest.raises(KeyboardInterrupt):
        editor_module.PerKeyEditor._on_close(editor)

    assert order == ["release", "destroy"]
