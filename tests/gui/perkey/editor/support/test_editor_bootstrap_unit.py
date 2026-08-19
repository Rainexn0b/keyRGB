"""Direct unit coverage for per-key editor_support.bootstrap.initialize_editor."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
        self.title_text = ""
        self.protocols: dict[str, object] = {}
        self.binds: list[tuple[str, object]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.idletasks = 0

    def title(self, text: str) -> None:
        self.title_text = text

    def update_idletasks(self) -> None:
        self.idletasks += 1

    def protocol(self, name: str, func: object) -> None:
        self.protocols[name] = func

    def bind(self, sequence: str, func: object) -> None:
        self.binds.append((sequence, func))

    def after(self, delay_ms: int, callback: object) -> str:
        self.after_calls.append((delay_ms, callback))
        return "after1"


class _Style:
    def __init__(self) -> None:
        self.configured: list[tuple[str, dict[str, object]]] = []
        self.mapped: list[tuple[str, dict[str, object]]] = []
        self.fail_map = False

    def configure(self, style_name: str, **kwargs: object) -> None:
        self.configured.append((style_name, kwargs))

    def lookup(self, style_name: str, option_name: str) -> str:
        return "#222222"

    def map(self, style_name: str, **kwargs: object) -> None:
        if self.fail_map:
            raise RuntimeError("map failed")
        self.mapped.append((style_name, kwargs))


class _Tk:
    def __init__(self) -> None:
        self.root = _Root()

    def Tk(self) -> _Root:
        return self.root

    def StringVar(self, value: object = "") -> _Var:
        return _Var(value)

    def BooleanVar(self, value: object = False) -> _Var:
        return _Var(value)

    def DoubleVar(self, value: object = 0.0) -> _Var:
        return _Var(value)


class _Ttk:
    def __init__(self) -> None:
        self.style = _Style()

    def Style(self) -> _Style:
        return self.style


class _Config:
    def __init__(self) -> None:
        self.physical_layout = "ansi"
        self.layout_legend_pack = "auto"
        self.color = (10, 20, 30)
        self.ac_perkey_profile_name = "Night"
        self.battery_perkey_profile_name = ""


def test_initialize_editor_wires_state_ui_and_initial_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    marked: list[object] = []
    monkeypatch.setattr(bootstrap.dirty_state, "mark_saved", lambda editor: marked.append(editor))

    tk = _Tk()
    ttk = _Ttk()
    app = SimpleNamespace(
        _detect_lightbar_device=lambda: True,
        _load_keymap=lambda: {"esc": ((0, 0),)},
        _load_layout_tweaks=lambda: {"scale": 1.0},
        _load_per_key_layout_tweaks=dict,
        _load_layout_slot_overrides=dict,
        _get_visible_layout_keys=lambda: [
            SimpleNamespace(key_id="missing", slot_id="m"),
            SimpleNamespace(key_id="esc", slot_id="slot_esc"),
        ],
        _reload_keymap=MagicMock(),
        select_slot_id=MagicMock(),
        _on_close=MagicMock(),
        canvas=SimpleNamespace(redraw=MagicMock()),
    )

    profiles = SimpleNamespace(
        get_active_profile=lambda: "Default",
        load_lightbar_overlay=lambda _n: {"enabled": True},
        load_secondary_lighting=lambda _n: {"version": 1, "areas": {}},
        load_backdrop_mode=lambda _n: "image",
        load_backdrop_transparency=lambda _n: 0.4,
    )

    status_msgs: list[str] = []
    geometry_fit_calls: list[dict[str, object]] = []
    icon_calls: list[object] = []
    theme_calls: list[dict[str, object]] = []
    build_ui = MagicMock()
    get_kb = MagicMock(return_value=object())

    bootstrap.initialize_editor(
        app,
        tk=tk,
        ttk=ttk,
        config_cls=_Config,
        profiles=profiles,
        apply_keyrgb_window_icon=lambda root: icon_calls.append(root),
        apply_perkey_editor_geometry=lambda root, **kwargs: None,
        compute_perkey_editor_min_content_size=lambda **kwargs: (800, 600),
        fit_perkey_editor_geometry_to_content=lambda root, **kwargs: geometry_fit_calls.append(kwargs),
        apply_clam_theme=lambda root, **kwargs: theme_calls.append(kwargs) or ("#111", "#eee"),
        tk_call_errors=(RuntimeError,),
        log_boundary_exception=MagicMock(),
        normalize_layout_legend_pack_fn=lambda layout, pack: f"{layout}:{pack or 'auto'}",
        initial_last_non_black_color=lambda color: (int(color[0]), int(color[1]), int(color[2])),
        load_profile_colors=lambda **kwargs: {(0, 0): (1, 2, 3)},
        sanitize_keymap_cells=lambda *a, **k: {},
        per_key_commit_pipeline_cls=lambda **kwargs: SimpleNamespace(interval=kwargs.get("commit_interval_s")),
        get_keyboard=get_kb,
        build_ui_fn=build_ui,
        set_status=lambda editor, msg: status_msgs.append(msg),
        no_keymap_found_initial=lambda: "no-map",
        num_rows=6,
        num_cols=21,
    )

    assert app.root is tk.root
    assert app.root.title_text.startswith("KeyRGB")
    assert icon_calls == [app.root]
    assert theme_calls and theme_calls[0]["include_checkbuttons"] is True
    assert app.bg_color == "#111"
    assert app.fg_color == "#eee"
    assert app.profile_name == "Default"
    assert app._physical_layout == "ansi"
    assert app._layout_legend_pack == "ansi:auto"
    assert app.has_lightbar_device is True
    assert app.lightbar_overlay == {"enabled": True}
    assert app.secondary_lighting == {"version": 1, "areas": {}}
    assert app.colors == {(0, 0): (1, 2, 3)}
    assert app.keymap == {"esc": ((0, 0),)}
    assert app._ac_power_source_profile_var.get() == "Night"
    assert app._battery_power_source_profile_var.get() == "Keep current profile"
    assert app.kb is get_kb.return_value
    build_ui.assert_called_once()
    assert "WM_DELETE_WINDOW" in app.root.protocols
    assert marked == [app]
    assert geometry_fit_calls  # immediate fit
    assert app.root.after_calls and app.root.after_calls[0][0] == 50
    app.canvas.redraw.assert_called()
    assert status_msgs == []  # keymap present
    app.select_slot_id.assert_called_once_with("slot_esc")
    assert any(seq == "<FocusIn>" for seq, _ in app.root.binds)

    # FocusIn binding reloads keymap
    focus_cb = next(cb for seq, cb in app.root.binds if seq == "<FocusIn>")
    focus_cb(None)
    app._reload_keymap.assert_called_once()


def test_initialize_editor_handles_style_map_failure_and_empty_keymap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bootstrap.dirty_state, "mark_saved", lambda _e: None)
    logs: list[str] = []
    tk = _Tk()
    ttk = _Ttk()
    ttk.style.fail_map = True

    app = SimpleNamespace(
        _detect_lightbar_device=lambda: False,
        _load_keymap=dict,
        _load_layout_tweaks=dict,
        _load_per_key_layout_tweaks=dict,
        _load_layout_slot_overrides=dict,
        _get_visible_layout_keys=list,
        _reload_keymap=MagicMock(),
        select_slot_id=MagicMock(),
        _on_close=MagicMock(),
        canvas=SimpleNamespace(redraw=MagicMock()),
    )
    profiles = SimpleNamespace(
        get_active_profile=lambda: "P",
        load_lightbar_overlay=lambda _n: {},
        # no load_secondary_lighting attribute
        load_backdrop_mode=lambda _n: "none",
        load_backdrop_transparency=lambda _n: 0.0,
    )
    # ensure attribute missing path
    assert not hasattr(profiles, "load_secondary_lighting")

    statuses: list[str] = []

    # Root without a callable protocol() method.
    class _RootBare:
        def title(self, text: str) -> None:
            pass

        def update_idletasks(self) -> None:
            pass

        def bind(self, sequence: str, func: object) -> None:
            pass

        def after(self, delay_ms: int, callback: object) -> None:
            pass

    tk.root = _RootBare()  # type: ignore[assignment]
    tk.Tk = lambda: tk.root  # type: ignore[method-assign]

    bootstrap.initialize_editor(
        app,
        tk=tk,
        ttk=ttk,
        config_cls=_Config,
        profiles=profiles,
        apply_keyrgb_window_icon=lambda _r: None,
        apply_perkey_editor_geometry=lambda _r, **_k: None,
        compute_perkey_editor_min_content_size=lambda **_k: (1, 1),
        fit_perkey_editor_geometry_to_content=lambda _r, **_k: None,
        apply_clam_theme=lambda _r, **_k: ("#000", "#fff"),
        tk_call_errors=(RuntimeError,),
        log_boundary_exception=lambda key, msg, exc: logs.append(key),
        normalize_layout_legend_pack_fn=lambda *_a: "auto",
        initial_last_non_black_color=lambda c: (1, 1, 1),
        load_profile_colors=lambda **_k: {},
        sanitize_keymap_cells=lambda *a, **k: {},
        per_key_commit_pipeline_cls=lambda **_k: object(),
        get_keyboard=lambda: None,
        build_ui_fn=lambda: None,
        set_status=lambda _e, msg: statuses.append(msg),
        no_keymap_found_initial=lambda: "no-map",
        num_rows=1,
        num_cols=1,
    )

    assert "perkey.editor.style_map" in logs
    assert app.secondary_lighting is None
    assert app.kb is None
    assert statuses == ["no-map"]
    app.select_slot_id.assert_not_called()
