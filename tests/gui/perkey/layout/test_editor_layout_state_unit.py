"""Direct unit coverage for per-key editor layout_state / layout helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.core.resources.layout_slots import LayoutSlotState
from src.gui.perkey.editor_support import layout as layout_mod, layout_state as layout_state_mod


class _Panel:
    def __init__(self) -> None:
        self.grid_calls = 0
        self.remove_calls = 0
        self.should_show = True

    def grid(self) -> None:
        self.grid_calls += 1

    def grid_remove(self) -> None:
        self.remove_calls += 1


class _Var:
    def __init__(self, value: str = "") -> None:
        self.value = value
        self.sets: list[object] = []

    def get(self) -> str:
        return self.value

    def set(self, value: object) -> None:
        self.sets.append(value)
        self.value = str(value)


def _slot(slot_id: str, key_id: str | None = None, *, label: str | None = None) -> LayoutSlotState:
    key = key_id or slot_id
    text = label or key
    return LayoutSlotState(
        slot_id=slot_id,
        key_id=key,
        label=text,
        visible=True,
        default_label=text,
        default_visible=True,
    )


def _make_app(**overrides: Any) -> SimpleNamespace:
    overlay_panel = _Panel()
    layout_panel = _Panel()
    lighting_panel = _Panel()
    base = {
        "profile_name": "Default",
        "_physical_layout": "ansi",
        "_layout_legend_pack": "auto",
        "selected_slot_id": None,
        "selected_key_id": None,
        "layout_slot_overrides": {},
        "layout_tweaks": {},
        "per_key_layout_tweaks": {},
        "keymap": {},
        "_setup_panel_mode": None,
        "config": SimpleNamespace(physical_layout="ansi", layout_legend_pack="auto"),
        "_layout_var": _Var("ansi"),
        "_legend_pack_var": _Var("auto"),
        "_overlay_setup_panel": overlay_panel,
        "_layout_setup_controls": layout_panel,
        "_lighting_areas_panel": lighting_panel,
        "overlay_controls": SimpleNamespace(sync_vars_from_scope=MagicMock()),
        "canvas": SimpleNamespace(redraw=MagicMock()),
        "lightbar_controls": SimpleNamespace(sync_vars_from_editor=MagicMock()),
    }
    base.update(overrides)
    app = SimpleNamespace(**base)

    # Bound method-style hooks used by layout helpers.
    app._normalize_layout_legend_pack = lambda layout_id, pack: layout_state_mod.normalize_layout_legend_pack(
        layout_id, pack, load_layout_legend_pack_fn=lambda _p: {"layout_id": layout_id}
    )
    app._resolved_layout_legend_pack_id = lambda: "ansi-default"
    app._sync_layout_legend_pack_ui = MagicMock()
    app._get_layout_slot_states = lambda: [_slot("esc"), _slot("a")]
    app._get_visible_layout_keys = lambda: [
        SimpleNamespace(slot_id="esc", key_id="esc"),
        SimpleNamespace(slot_id="a", key_id="a"),
    ]
    app._slot_id_for_key_id = lambda key_id: key_id
    app._clear_selection = MagicMock()
    app.select_slot_id = MagicMock()
    app._refresh_selected_cells = MagicMock()
    app._load_keymap = MagicMock(return_value={"esc": ((0, 0),)})
    app._load_layout_tweaks = MagicMock(return_value={"scale": 1.0})
    app._load_per_key_layout_tweaks = MagicMock(return_value={})
    app._load_layout_slot_overrides = MagicMock(return_value={})
    app._persist_layout_slot_overrides = MagicMock()
    app._refresh_layout_slot_controls = MagicMock()
    app._sync_visible_layout_state = MagicMock()
    app._layout_slot_state_for_identity = lambda identity: next(
        (s for s in app._get_layout_slot_states() if identity in {s.slot_id, s.key_id}),
        None,
    )
    app._hide_setup_panel = lambda: layout_mod.hide_setup_panel(app)
    app._show_setup_panel = lambda mode: layout_mod.show_setup_panel(app, mode)
    return app


def test_normalize_and_resolved_legend_pack() -> None:
    assert layout_state_mod.normalize_layout_legend_pack("ansi", None) == "auto"
    assert layout_state_mod.normalize_layout_legend_pack("ansi", "auto") == "auto"
    assert (
        layout_state_mod.normalize_layout_legend_pack(
            "ansi",
            "pack-a",
            load_layout_legend_pack_fn=lambda _p: None,
        )
        == "auto"
    )
    assert (
        layout_state_mod.normalize_layout_legend_pack(
            "ansi",
            "pack-a",
            load_layout_legend_pack_fn=lambda _p: {"layout_id": "iso"},
        )
        == "auto"
    )
    assert (
        layout_state_mod.normalize_layout_legend_pack(
            "ansi",
            "pack-a",
            load_layout_legend_pack_fn=lambda _p: {"layout_id": "ansi"},
        )
        == "pack-a"
    )

    app = _make_app(_layout_legend_pack="pack-a", _physical_layout="ansi")
    resolved = layout_state_mod.resolved_layout_legend_pack_id(
        app,
        resolve_layout_legend_pack_id_fn=lambda layout, pack: f"{layout}:{pack}",
    )
    assert resolved == "ansi:pack-a"


def test_selected_overlay_and_slot_lookup() -> None:
    app = _make_app(selected_slot_id="esc", selected_key_id="a")
    assert layout_state_mod.selected_overlay_identity(app) == "esc"
    app.selected_slot_id = None
    assert layout_state_mod.selected_overlay_identity(app) == "a"

    assert layout_state_mod.layout_slot_state_for_identity(app, None) is None
    state = layout_state_mod.layout_slot_state_for_identity(app, "a")
    assert state is not None
    assert state.slot_id == "a"
    assert layout_state_mod.layout_slot_state_for_identity(app, "missing") is None


def test_sync_visible_layout_state_clears_hidden_selection() -> None:
    app = _make_app(selected_slot_id="gone")
    layout_state_mod.sync_visible_layout_state(
        app,
        keymap_cells_for_fn=lambda *_a, **_k: ((0, 0),),
    )
    app._clear_selection.assert_called_once()
    app.select_slot_id.assert_called_once_with("esc")


def test_sync_visible_layout_state_refreshes_visible_selection() -> None:
    app = _make_app(selected_slot_id="a")
    layout_state_mod.sync_visible_layout_state(
        app,
        keymap_cells_for_fn=lambda *_a, **_k: (),
    )
    app._clear_selection.assert_not_called()
    app._refresh_selected_cells.assert_called_once()
    assert app.selected_slot_id == "a"


def test_detect_lightbar_device_success_and_errors() -> None:
    logs: list[str] = []

    assert (
        layout_state_mod.detect_lightbar_device(
            collect_device_discovery=lambda *, include_usb: {
                "supported": [{"device_type": "keyboard"}],
                "candidates": [{"device_type": "lightbar"}],
            },
            log_boundary_exception=lambda *_a: logs.append("x"),
        )
        is True
    )

    assert (
        layout_state_mod.detect_lightbar_device(
            collect_device_discovery=lambda *, include_usb: {"supported": "bad", "candidates": []},
            log_boundary_exception=lambda *_a: None,
        )
        is False
    )

    def boom(*, include_usb: bool) -> dict[str, object]:
        raise OSError("denied")

    assert (
        layout_state_mod.detect_lightbar_device(
            collect_device_discovery=boom,
            log_boundary_exception=lambda *_a: logs.append("err"),
        )
        is False
    )
    assert logs == ["err"]


def test_load_helpers_delegate_to_profiles() -> None:
    app = _make_app()
    profiles = SimpleNamespace(
        load_layout_slots=MagicMock(return_value={"esc": {"visible": False}}),
        load_layout_global=MagicMock(return_value={"scale": 2.0}),
        load_layout_per_key=MagicMock(return_value={"esc": {"dx": 1.0}}),
    )
    assert layout_state_mod.load_layout_slot_overrides(app, profiles_module=profiles) == {"esc": {"visible": False}}
    assert layout_state_mod.load_layout_tweaks(app, profiles_module=profiles) == {"scale": 2.0}
    assert layout_state_mod.load_per_key_layout_tweaks(app, profiles_module=profiles) == {"esc": {"dx": 1.0}}


def test_set_layout_slot_visibility_and_label(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses: list[str] = []
    monkeypatch.setattr(layout_mod, "set_status", lambda _app, msg: statuses.append(msg))
    monkeypatch.setattr(layout_mod, "layout_slot_visibility_updated", lambda key, vis: f"vis:{key}:{vis}")
    monkeypatch.setattr(layout_mod, "layout_slot_label_updated", lambda key, label: f"label:{key}:{label}")

    app = _make_app(layout_slot_overrides={})
    layout_mod.set_layout_slot_visibility(app, "esc", False)
    assert app.layout_slot_overrides["esc"]["visible"] is False
    app._persist_layout_slot_overrides.assert_called()
    app.canvas.redraw.assert_called()
    assert statuses[-1] == "vis:esc:False"

    layout_mod.set_layout_slot_visibility(app, "esc", True)
    assert "esc" not in app.layout_slot_overrides

    layout_mod.set_layout_slot_label(app, "a", "Alpha")
    assert app.layout_slot_overrides["a"]["label"] == "Alpha"
    layout_mod.set_layout_slot_label(app, "a", "a")  # back to default
    assert "a" not in app.layout_slot_overrides
    assert any(s.startswith("label:") for s in statuses)


def test_on_layout_and_legend_pack_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    paths = SimpleNamespace(
        keymap=SimpleNamespace(exists=lambda: False),
        layout_global=SimpleNamespace(exists=lambda: False),
        layout_per_key=SimpleNamespace(exists=lambda: True),
    )
    monkeypatch.setattr(layout_mod.profiles, "paths_for", lambda _name: paths)

    app._layout_var.value = "iso"
    app._setup_panel_mode = "overlay"
    layout_mod.on_layout_changed(app)

    assert app._physical_layout == "iso"
    assert app.config.physical_layout == "iso"
    app._load_keymap.assert_called_once()
    app._load_layout_tweaks.assert_called_once()
    app._load_per_key_layout_tweaks.assert_not_called()
    app.overlay_controls.sync_vars_from_scope.assert_called()
    app.canvas.redraw.assert_called()

    app._legend_pack_var.value = "pack-x"
    layout_mod.on_layout_legend_pack_changed(app)
    assert app.config.layout_legend_pack == app._layout_legend_pack
    app._sync_visible_layout_state.assert_called()


def test_setup_panel_toggle_and_show_hide() -> None:
    app = _make_app()
    layout_mod.show_setup_panel(app, "overlay")
    assert app._setup_panel_mode == "overlay"
    assert app._overlay_setup_panel.grid_calls >= 1
    app.overlay_controls.sync_vars_from_scope.assert_called()
    app.lightbar_controls.sync_vars_from_editor.assert_called()

    layout_mod.hide_setup_panel(app)
    assert app._setup_panel_mode is None
    assert app._lighting_areas_panel.grid_calls >= 1

    layout_mod.show_setup_panel(app, "layout")
    assert app._setup_panel_mode == "layout"
    app._refresh_layout_slot_controls.assert_called()

    layout_mod.toggle_overlay(app)
    assert app._setup_panel_mode == "overlay"
    layout_mod.toggle_overlay(app)
    assert app._setup_panel_mode is None

    layout_mod.toggle_layout_setup(app)
    assert app._setup_panel_mode == "layout"
    layout_mod.toggle_layout_setup(app)
    assert app._setup_panel_mode is None


def test_sync_layout_legend_pack_ui_and_helpers() -> None:
    app = _make_app()
    logs: list[str] = []
    refreshed: list[str] = []

    class _Controls:
        def refresh_legend_pack_choices(self) -> None:
            refreshed.append("ok")

    app._layout_setup_controls = _Controls()  # type: ignore[assignment]
    app._legend_pack_var = _Var("auto")

    layout_state_mod.sync_layout_legend_pack_ui(
        app,
        tk_call_errors=(RuntimeError,),
        log_boundary_exception=lambda *_a: logs.append("x"),
    )
    assert app._legend_pack_var.sets == ["auto"]
    assert refreshed == ["ok"]

    # AttributeError path for missing layout setup controls
    broken = SimpleNamespace()
    assert layout_state_mod._layout_setup_controls_or_none(broken) is None  # type: ignore[arg-type]
    assert layout_state_mod._refresh_legend_pack_choices_or_none(object()) is None

    layout_state_mod.refresh_layout_slot_controls(app, refresh_layout_slots_ui_fn=lambda a: refreshed.append("slots"))
    assert "slots" in refreshed

    states = layout_state_mod.get_layout_slot_states_for_editor(
        app,
        get_layout_slot_states_fn=lambda *_a, **_k: [_slot("esc")],
    )
    assert states[0].slot_id == "esc"
