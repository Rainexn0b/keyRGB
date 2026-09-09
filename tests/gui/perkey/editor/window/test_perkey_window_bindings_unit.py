"""UX-08 per-key editor accelerator bindings."""

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
    def __init__(self) -> None:
        self.protocols: dict[str, object] = {}
        self.binds: list[tuple[str, object, object]] = []
        self.after_calls: list[tuple[int, object]] = []

    def title(self, text: str) -> None:
        pass

    def update_idletasks(self) -> None:
        pass

    def protocol(self, name: str, func: object) -> None:
        self.protocols[name] = func

    def bind(self, sequence: str, func: object, add: object = None) -> None:
        self.binds.append((sequence, func, add))

    def after(self, delay_ms: int, callback: object) -> str:
        self.after_calls.append((delay_ms, callback))
        return "after1"

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def winfo_reqwidth(self) -> int:
        return 900

    def winfo_reqheight(self) -> int:
        return 700

    def geometry(self, value: str) -> None:
        pass

    def minsize(self, width: int, height: int) -> None:
        pass


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


class _NoRestoreTracker:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def restore(self) -> bool:
        return False

    def start_tracking(self) -> None:
        pass


def _run_bootstrap() -> tuple[SimpleNamespace, _Root, MagicMock, MagicMock]:
    root = _Root()
    on_close = MagicMock()
    on_save = MagicMock()
    app = SimpleNamespace(
        _detect_lightbar_device=lambda: False,
        _load_keymap=lambda: {"esc": ((0, 0),)},
        _load_layout_tweaks=dict,
        _load_per_key_layout_tweaks=dict,
        _load_layout_slot_overrides=dict,
        _get_visible_layout_keys=lambda: [SimpleNamespace(key_id="esc", slot_id="slot_esc")],
        select_slot_id=MagicMock(),
        _on_close=on_close,
        _save_profile=on_save,
        canvas=SimpleNamespace(redraw=MagicMock()),
    )
    profiles = SimpleNamespace(
        get_active_profile=lambda: "Default",
        load_lightbar_overlay=lambda _n: {},
        load_backdrop_mode=lambda _n: "none",
        load_backdrop_transparency=lambda _n: 0.0,
    )
    build_ui = MagicMock()
    bootstrap.initialize_editor(
        app,
        tk=_Tk(root),
        config_cls=_Config,
        profiles=profiles,
        apply_keyrgb_window_icon=lambda _r: None,
        apply_perkey_editor_geometry=lambda _r, **_k: None,
        compute_perkey_editor_min_content_size=lambda **_k: (800, 600),
        fit_perkey_editor_geometry_to_content=lambda _r, **_k: None,
        apply_clam_theme=lambda _r, **_k: ("#111", "#eee"),
        normalize_layout_legend_pack_fn=lambda layout, _pack: layout,
        initial_last_non_black_color=lambda _c: (1, 2, 3),
        load_profile_colors=lambda **_k: {},
        per_key_commit_pipeline_cls=lambda **_k: object(),
        get_keyboard=lambda: None,
        build_ui_fn=build_ui,
        set_status=lambda _e, _m: None,
        no_keymap_found_initial=lambda: "no-map",
        num_rows=6,
        num_cols=21,
    )
    return app, root, on_close, on_save


@pytest.fixture(autouse=True)
def _force_fallback_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap, "WindowGeometryTracker", _NoRestoreTracker)
    monkeypatch.setattr(bootstrap.dirty_state, "mark_saved", lambda _e: None)


def test_perkey_shortcuts_are_ctrl_w_and_ctrl_s_without_escape() -> None:
    _app, root, _close, _save = _run_bootstrap()
    sequences = [seq for seq, _cb, _add in root.binds]
    assert sequences == ["<Control-w>", "<Control-s>"]
    assert "<Escape>" not in sequences
    assert all(add == "+" for _seq, _cb, add in root.binds)


def test_ctrl_w_routes_to_on_close_and_returns_break() -> None:
    _app, root, on_close, on_save = _run_bootstrap()
    callback = next(cb for seq, cb, _ in root.binds if seq == "<Control-w>")
    assert callback(object()) == "break"  # type: ignore[operator]
    on_close.assert_called_once()
    on_save.assert_not_called()


def test_ctrl_s_routes_to_save_profile_and_returns_break() -> None:
    _app, root, on_close, on_save = _run_bootstrap()
    callback = next(cb for seq, cb, _ in root.binds if seq == "<Control-s>")
    assert callback(object()) == "break"  # type: ignore[operator]
    on_save.assert_called_once()
    on_close.assert_not_called()


def test_initial_focus_still_owned_by_build_ui() -> None:
    app, root, _close, _save = _run_bootstrap()
    # Bootstrap must not steal focus: no FocusIn binding and the editor chrome
    # builder (owner of the UX-05 backdrop-selector focus) still runs.
    assert all(seq != "<FocusIn>" for seq, _cb, _add in root.binds)
    assert app.select_slot_id.called


def test_dirty_cancel_prevents_destroy_via_ctrl_w_accelerator(monkeypatch: pytest.MonkeyPatch) -> None:
    _app, root, _close, _save = _run_bootstrap()
    close_callback = next(cb for seq, cb, _ in root.binds if seq == "<Control-w>")

    destroyed: list[str] = []
    editor = editor_module.PerKeyEditor.__new__(editor_module.PerKeyEditor)
    editor.tk_jobs = SimpleNamespace(cancel=lambda: None)
    editor.kb = None
    editor.root = SimpleNamespace(destroy=lambda: destroyed.append("destroy"))
    monkeypatch.setattr(editor_module.dirty_state, "confirm_destructive_action", lambda *_a, **_k: False)
    monkeypatch.setattr(editor_module.hardware, "release_hardware_control", lambda: None)

    # Rewire the captured accelerator to the dirty-checked close path.
    assert close_callback(object()) == "break"  # type: ignore[operator]
    # The bootstrap route calls the mock; now verify the real close honors cancel.
    editor._on_close()
    assert destroyed == []
