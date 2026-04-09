from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.resources.layout import BASE_IMAGE_SIZE, KeyDef
from src.core.resources.layouts import slot_id_for_key_id
from src.gui.calibrator import app as calibrator_app
from src.gui.calibrator.helpers.probe import CalibrationProbeState
from src.gui.reference.overlay_geometry import CanvasTransform


class _FakeLabel:
    def __init__(self, text: str = "") -> None:
        self.options: dict[str, object] = {"text": text}
        self.configure_calls: list[dict[str, object]] = []

    @property
    def text(self) -> str:
        return str(self.options.get("text", ""))

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)


class _FakePreview:
    def __init__(self) -> None:
        self.apply_probe_calls: list[tuple[int, int]] = []
        self.restore_calls = 0

    def apply_probe_cell(self, row: int, col: int) -> None:
        self.apply_probe_calls.append((row, col))

    def restore(self) -> None:
        self.restore_calls += 1


class _FakeDeckRenderCache:
    def __init__(self) -> None:
        self.clear_calls = 0

    def clear(self) -> None:
        self.clear_calls += 1


def _make_app(**overrides: object) -> SimpleNamespace:
    after_calls: list[tuple[int, object]] = []
    destroy_calls: list[str] = []
    app = SimpleNamespace(
        profile_name="gaming",
        lbl_status=_FakeLabel("initial"),
        lbl_cell=_FakeLabel(),
        preview=_FakePreview(),
        probe=CalibrationProbeState(rows=2, cols=3),
        keymap={},
        layout_tweaks={"dx": 1.0},
        per_key_layout_tweaks={"esc": {"dx": 0.5}},
        layout_slot_overrides={"macro": {"enabled": True}},
        cfg=SimpleNamespace(physical_layout="ansi", layout_legend_pack="auto"),
        canvas="canvas",
        _deck_pil=None,
        _deck_tk="stale-tk-image",
        _deck_render_cache=_FakeDeckRenderCache(),
        _transform=None,
        after=lambda delay_ms, callback: after_calls.append((delay_ms, callback)),
        destroy=lambda: destroy_calls.append("destroy"),
    )
    for name, value in overrides.items():
        setattr(app, name, value)
    app.after_calls = after_calls
    app.destroy_calls = destroy_calls
    return app


def test_keymap_path_uses_active_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(calibrator_app, "get_active_profile_name", lambda: "profile-z")
    monkeypatch.setattr(calibrator_app, "keymap_path", lambda profile_name: tmp_path / f"{profile_name}.json")

    assert calibrator_app._keymap_path() == tmp_path / "profile-z.json"


def test_save_keymap_uses_active_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, tuple[tuple[int, int], ...]]]] = []
    keymap = {"esc": ((0, 0),)}

    monkeypatch.setattr(calibrator_app, "get_active_profile_name", lambda: "profile-z")
    monkeypatch.setattr(
        calibrator_app,
        "save_keymap",
        lambda profile_name, value, **kwargs: calls.append((profile_name, value, kwargs)),
    )

    calibrator_app._save_keymap(keymap)

    assert calls == [("profile-z", keymap, {"physical_layout": None})]


def test_load_profile_state_uses_selected_physical_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, str | None]] = []

    def fake_load_keymap(profile_name: str, *, physical_layout: str | None = None) -> dict[str, object]:
        calls.append(("keymap", profile_name, physical_layout))
        return {"iso_extra": (0, 1), "invalid": (99, 99), "enter": [(1, 2), (1, 3)]}

    def fake_load_layout_global(profile_name: str, *, physical_layout: str | None = None) -> dict[str, float]:
        calls.append(("layout_global", profile_name, physical_layout))
        return {"dx": 1.5}

    def fake_load_layout_per_key(
        profile_name: str,
        *,
        physical_layout: str | None = None,
    ) -> dict[str, dict[str, float]]:
        calls.append(("layout_per_key", profile_name, physical_layout))
        return {"iso_extra": {"dx": 0.25}}

    def fake_load_layout_slots(profile_name: str, physical_layout: str) -> dict[str, dict[str, object]]:
        calls.append(("layout_slots", profile_name, physical_layout))
        return {"nonusbackslash": {"label": "<>"}}

    monkeypatch.setattr(calibrator_app, "load_keymap", fake_load_keymap)
    monkeypatch.setattr(calibrator_app, "load_layout_global", fake_load_layout_global)
    monkeypatch.setattr(calibrator_app, "load_layout_per_key", fake_load_layout_per_key)
    monkeypatch.setattr(calibrator_app, "load_layout_slots", fake_load_layout_slots)

    keymap, layout_tweaks, per_key_layout_tweaks, layout_slot_overrides = calibrator_app._load_profile_state(
        "profile-z",
        physical_layout="iso",
    )

    assert calls == [
        ("keymap", "profile-z", "iso"),
        ("layout_global", "profile-z", "iso"),
        ("layout_per_key", "profile-z", "iso"),
        ("layout_slots", "profile-z", "iso"),
    ]
    assert keymap == {"iso_extra": ((0, 1),), "enter": ((1, 2), (1, 3))}
    assert layout_tweaks == {"dx": 1.5}
    assert per_key_layout_tweaks == {"iso_extra": {"dx": 0.25}}
    assert layout_slot_overrides == {"nonusbackslash": {"label": "<>"}}


def test_set_backdrop_saves_reloads_and_redraws_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    calls: list[tuple[str, str]] = []
    mode_calls: list[tuple[str, str]] = []
    actions: list[str] = []
    app._load_deck_image = lambda: actions.append("load")
    app._redraw = lambda: actions.append("redraw")
    app._backdrop_mode_var = type("Var", (), {"set": lambda self, value: None})()
    app._backdrop_mode_combo = type("Combo", (), {"set": lambda self, value: None})()

    monkeypatch.setattr(calibrator_app.filedialog, "askopenfilename", lambda **_kwargs: "/tmp/deck.png")
    monkeypatch.setattr(
        calibrator_app,
        "save_backdrop_image",
        lambda *, profile_name, source_path: calls.append((profile_name, source_path)),
    )
    monkeypatch.setattr(
        calibrator_app.profiles, "save_backdrop_mode", lambda mode, name: mode_calls.append((mode, name))
    )

    calibrator_app.KeymapCalibrator._set_backdrop(app)

    assert calls == [("gaming", "/tmp/deck.png")]
    assert mode_calls == [("custom", "gaming")]
    assert actions == ["load", "redraw"]
    assert app.lbl_status.text == "Backdrop updated"


def test_set_backdrop_returns_early_when_picker_is_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    actions: list[str] = []
    app._load_deck_image = lambda: actions.append("load")
    app._redraw = lambda: actions.append("redraw")

    monkeypatch.setattr(calibrator_app.filedialog, "askopenfilename", lambda **_kwargs: "")
    monkeypatch.setattr(
        calibrator_app,
        "save_backdrop_image",
        lambda **_kwargs: actions.append("save"),
    )

    calibrator_app.KeymapCalibrator._set_backdrop(app)

    assert actions == []
    assert app.lbl_status.text == "initial"


def test_set_backdrop_reports_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    actions: list[str] = []
    app._load_deck_image = lambda: actions.append("load")
    app._redraw = lambda: actions.append("redraw")

    monkeypatch.setattr(calibrator_app.filedialog, "askopenfilename", lambda **_kwargs: "/tmp/deck.png")

    def fake_save_backdrop_image(**_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(calibrator_app, "save_backdrop_image", fake_save_backdrop_image)

    calibrator_app.KeymapCalibrator._set_backdrop(app)

    assert actions == []
    assert app.lbl_status.text == "Failed to set backdrop"


def test_reset_backdrop_reloads_and_redraws_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    reset_calls: list[str] = []
    mode_calls: list[tuple[str, str]] = []
    actions: list[str] = []
    app._load_deck_image = lambda: actions.append("load")
    app._redraw = lambda: actions.append("redraw")
    app._backdrop_mode_var = type("Var", (), {"set": lambda self, value: None})()
    app._backdrop_mode_combo = type("Combo", (), {"set": lambda self, value: None})()

    monkeypatch.setattr(calibrator_app, "reset_backdrop_image", lambda profile_name: reset_calls.append(profile_name))
    monkeypatch.setattr(
        calibrator_app.profiles, "save_backdrop_mode", lambda mode, name: mode_calls.append((mode, name))
    )

    calibrator_app.KeymapCalibrator._reset_backdrop(app)

    assert reset_calls == ["gaming"]
    assert mode_calls == [("builtin", "gaming")]
    assert actions == ["load", "redraw"]
    assert app.lbl_status.text == "Backdrop reset"


def test_reset_backdrop_reports_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    actions: list[str] = []
    app._load_deck_image = lambda: actions.append("load")
    app._redraw = lambda: actions.append("redraw")

    def fake_reset_backdrop_image(_profile_name: str) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(calibrator_app, "reset_backdrop_image", fake_reset_backdrop_image)

    calibrator_app.KeymapCalibrator._reset_backdrop(app)

    assert actions == []
    assert app.lbl_status.text == "Failed to reset backdrop"


def test_on_backdrop_mode_changed_persists_reload_and_redraws(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    actions: list[str] = []
    app._load_deck_image = lambda: actions.append("load")
    app._redraw = lambda: actions.append("redraw")
    app._backdrop_mode_var = type(
        "Var",
        (),
        {
            "value": "builtin",
            "set": lambda self, value: setattr(self, "value", value),
            "get": lambda self: self.value,
        },
    )()
    app._backdrop_mode_combo = type("Combo", (), {"get": lambda self: "No backdrop"})()
    mode_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        calibrator_app.profiles, "save_backdrop_mode", lambda mode, name: mode_calls.append((mode, name))
    )

    calibrator_app.KeymapCalibrator._on_backdrop_mode_changed(app)

    assert mode_calls == [("none", "gaming")]
    assert app._backdrop_mode_var.get() == "none"
    assert actions == ["load", "redraw"]


def test_on_backdrop_mode_changed_reports_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    actions: list[str] = []
    app._load_deck_image = lambda: actions.append("load")
    app._redraw = lambda: actions.append("redraw")
    app._backdrop_mode_var = type(
        "Var",
        (),
        {
            "value": "builtin",
            "set": lambda self, value: setattr(self, "value", value),
            "get": lambda self: self.value,
        },
    )()
    app._backdrop_mode_combo = type("Combo", (), {"get": lambda self: "Custom image"})()

    monkeypatch.setattr(
        calibrator_app.profiles,
        "save_backdrop_mode",
        lambda mode, name: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    calibrator_app.KeymapCalibrator._on_backdrop_mode_changed(app)

    assert actions == []
    assert app.lbl_status.text == "Failed to update backdrop mode"


def test_restore_original_config_calls_preview_restore() -> None:
    app = _make_app()

    calibrator_app.KeymapCalibrator._restore_original_config(app)

    assert app.preview.restore_calls == 1


def test_on_close_restores_config_then_destroys() -> None:
    app = _make_app()
    calls: list[str] = []
    app._restore_original_config = lambda: calls.append("restore")
    app.destroy = lambda: calls.append("destroy")

    calibrator_app.KeymapCalibrator._on_close(app)

    assert calls == ["restore", "destroy"]


def test_load_deck_image_loads_backdrop_and_clears_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    image = object()
    calls: list[str] = []

    def fake_load_backdrop_image(profile_name: str) -> object:
        calls.append(profile_name)
        return image

    monkeypatch.setattr(calibrator_app, "load_backdrop_image", fake_load_backdrop_image)

    calibrator_app.KeymapCalibrator._load_deck_image(app)

    assert calls == ["gaming"]
    assert app._deck_pil is image
    assert app._deck_render_cache.clear_calls == 1


def test_apply_current_probe_updates_label_applies_preview_and_schedules_after() -> None:
    app = _make_app()
    app.probe.current_cell = (1, 2)

    calibrator_app.KeymapCalibrator._apply_current_probe(app)

    assert app.lbl_cell.text == "Probing matrix cell: (1, 2)"
    assert app.preview.apply_probe_calls == [(1, 2)]
    assert len(app.after_calls) == 1
    delay_ms, callback = app.after_calls[0]
    assert delay_ms == 50
    assert callable(callback)


@pytest.mark.parametrize(
    ("method_name", "probe_method"),
    [("_prev", "prev_cell"), ("_next", "next_cell")],
)
def test_prev_and_next_step_probe_and_reapply(
    method_name: str,
    probe_method: str,
) -> None:
    calls: list[str] = []
    probe = SimpleNamespace(
        prev_cell=lambda: calls.append("prev_cell"),
        next_cell=lambda: calls.append("next_cell"),
    )
    app = _make_app(probe=probe)
    app._apply_current_probe = lambda: calls.append("apply")

    getattr(calibrator_app.KeymapCalibrator, method_name)(app)

    assert calls == [probe_method, "apply"]


def test_skip_clears_selection_updates_status_and_moves_next() -> None:
    calls: list[str] = []
    probe = SimpleNamespace(clear_selection=lambda: calls.append("clear_selection"))
    app = _make_app(probe=probe)
    app._next = lambda: calls.append("next")

    calibrator_app.KeymapCalibrator._skip(app)

    assert calls == ["clear_selection", "next"]
    assert app.lbl_status.text == "Skipped. Move to next cell."


def test_assign_requires_selected_key() -> None:
    app = _make_app(probe=SimpleNamespace(selected_key_id=None, selected_slot_id=None, current_cell=(1, 1)), keymap={})
    calls: list[str] = []
    app._redraw = lambda: calls.append("redraw")
    app._next = lambda: calls.append("next")

    calibrator_app.KeymapCalibrator._assign(app)

    assert app.keymap == {}
    assert calls == []
    assert app.lbl_status.text == "Select a key on the image first"


def test_assign_updates_keymap_redraws_and_advances() -> None:
    app = _make_app(
        probe=SimpleNamespace(selected_key_id="esc", selected_slot_id="esc", current_cell=(1, 2)), keymap={}
    )
    calls: list[str] = []
    app._redraw = lambda: calls.append("redraw")
    app._next = lambda: calls.append("next")

    calibrator_app.KeymapCalibrator._assign(app)

    assert app.keymap == {"esc": ((1, 2),)}
    assert app.lbl_status.text == "Assigned esc -> (1, 2) (1 cell(s))"
    assert calls == ["redraw", "next"]


def test_assign_appends_unique_cells_for_existing_key() -> None:
    app = _make_app(
        probe=SimpleNamespace(selected_key_id="esc", selected_slot_id="esc", current_cell=(1, 3)),
        keymap={"esc": ((1, 2),)},
    )
    calls: list[str] = []
    app._redraw = lambda: calls.append("redraw")
    app._next = lambda: calls.append("next")

    calibrator_app.KeymapCalibrator._assign(app)

    assert app.keymap == {"esc": ((1, 2), (1, 3))}
    assert app.lbl_status.text == "Assigned esc -> (1, 3) (2 cell(s))"
    assert calls == ["redraw", "next"]


def test_assign_rehomes_physical_cell_from_previous_owner() -> None:
    app = _make_app(
        probe=SimpleNamespace(selected_key_id="esc", selected_slot_id="esc", current_cell=(1, 2)),
        keymap={"esc": ((0, 1),), "f1": ((1, 2),)},
    )
    calls: list[str] = []
    app._redraw = lambda: calls.append("redraw")
    app._next = lambda: calls.append("next")

    calibrator_app.KeymapCalibrator._assign(app)

    assert app.keymap == {"esc": ((0, 1), (1, 2))}
    assert app.lbl_status.text == "Assigned esc -> (1, 2) (2 cell(s))"
    assert calls == ["redraw", "next"]


def test_assign_uses_selected_slot_id_as_primary_identity() -> None:
    app = _make_app(
        probe=SimpleNamespace(selected_key_id=None, selected_slot_id="top_01", current_cell=(0, 4)),
        keymap={"top_01": ((0, 2),)},
        cfg=SimpleNamespace(physical_layout="ansi", layout_legend_pack="auto"),
    )
    calls: list[str] = []
    app._redraw = lambda: calls.append("redraw")
    app._next = lambda: calls.append("next")

    calibrator_app.KeymapCalibrator._assign(app)

    assert app.keymap == {"top_01": ((0, 2), (0, 4))}
    assert app.lbl_status.text == "Assigned q -> (0, 4) (2 cell(s))"
    assert calls == ["redraw", "next"]


def test_assign_canonicalizes_selected_slot_identity_and_drops_key_alias() -> None:
    app = _make_app(
        probe=SimpleNamespace(selected_key_id="q", selected_slot_id="top_01", current_cell=(0, 4)),
        keymap={"q": ((0, 2),)},
        cfg=SimpleNamespace(physical_layout="ansi", layout_legend_pack="auto"),
    )
    calls: list[str] = []
    app._redraw = lambda: calls.append("redraw")
    app._next = lambda: calls.append("next")

    calibrator_app.KeymapCalibrator._assign(app)

    assert app.keymap == {"top_01": ((0, 2), (0, 4))}
    assert app.lbl_status.text == "Assigned q -> (0, 4) (2 cell(s))"
    assert calls == ["redraw", "next"]


def test_assign_resolves_stale_neighbor_overlap_using_layout_defaults() -> None:
    app = _make_app(
        probe=SimpleNamespace(selected_key_id="rctrl", selected_slot_id="bottom_07", current_cell=(0, 13)),
        keymap={"bottom_06": ((0, 12), (0, 11)), "bottom_07": ((0, 11), (0, 12))},
        cfg=SimpleNamespace(physical_layout="iso", layout_legend_pack="auto"),
    )
    calls: list[str] = []
    app._redraw = lambda: calls.append("redraw")
    app._next = lambda: calls.append("next")

    calibrator_app.KeymapCalibrator._assign(app)

    assert app.keymap == {"bottom_06": ((0, 12),), "bottom_07": ((0, 11), (0, 13))}
    assert app.lbl_status.text == "Assigned rctrl -> (0, 13) (2 cell(s))"
    assert calls == ["redraw", "next"]


def test_reset_keymap_defaults_restores_layout_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app(keymap={"old": ((4, 4),)}, cfg=SimpleNamespace(physical_layout="iso"))
    calls: list[str] = []
    app._redraw = lambda: calls.append("redraw")

    monkeypatch.setattr(calibrator_app, "_parse_default_keymap", lambda layout_id: {"iso_extra": ((0, 1),)})
    monkeypatch.setattr(calibrator_app, "_resolved_layout_label", lambda layout_id: "ISO (102/105-key)")

    calibrator_app.KeymapCalibrator._reset_keymap_defaults(app)

    assert app.keymap == {"iso_extra": ((0, 1),)}
    assert app.lbl_status.text == "Reset keymap to ISO (102/105-key) defaults"
    assert calls == ["redraw"]


def test_save_persists_keymap_and_reports_path(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app(keymap={"esc": ((0, 0),)})
    save_calls: list[dict[str, tuple[tuple[int, int], ...]]] = []

    monkeypatch.setattr(
        calibrator_app, "_save_keymap", lambda keymap, **kwargs: save_calls.append((dict(keymap), kwargs))
    )
    monkeypatch.setattr(calibrator_app, "_keymap_path", lambda: Path("/tmp/profile/keymap.json"))

    calibrator_app.KeymapCalibrator._save(app)

    assert save_calls == [({"esc": ((0, 0),)}, {"physical_layout": "ansi"})]
    assert app.lbl_status.text == "Saved to /tmp/profile/keymap.json"


def test_save_and_close_saves_restores_and_destroys() -> None:
    app = _make_app()
    calls: list[str] = []
    app._save = lambda: calls.append("save")
    app._restore_original_config = lambda: calls.append("restore")
    app.destroy = lambda: calls.append("destroy")

    calibrator_app.KeymapCalibrator._save_and_close(app)

    assert calls == ["save", "restore", "destroy"]


def test_redraw_delegates_to_canvas_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app(
        keymap={"esc": (0, 0)},
        probe=SimpleNamespace(selected_key_id="esc", selected_slot_id=None),
        _deck_pil="deck-image",
        _deck_render_cache="cache",
    )
    calls: list[dict[str, object]] = []
    transform = object()
    tk_image = object()

    def fake_redraw_calibration_canvas(**kwargs: object) -> tuple[object, object]:
        calls.append(dict(kwargs))
        return transform, tk_image

    monkeypatch.setattr(calibrator_app, "redraw_calibration_canvas", fake_redraw_calibration_canvas)

    calibrator_app.KeymapCalibrator._redraw(app)

    assert len(calls) == 1
    assert calls[0] == {
        "canvas": "canvas",
        "deck_pil": "deck-image",
        "deck_render_cache": "cache",
        "layout_tweaks": {"dx": 1.0},
        "per_key_layout_tweaks": {"esc": {"dx": 0.5}},
        "keymap": {"esc": (0, 0)},
        "selected_slot_id": str(slot_id_for_key_id("ansi", "esc") or "esc"),
        "selected_key_id": "esc",
        "physical_layout": "ansi",
        "legend_pack_id": None,
        "slot_overrides": {"macro": {"enabled": True}},
    }
    assert app._transform is transform
    assert app._deck_tk is tk_image


def test_on_click_clears_selection_when_no_key_is_hit() -> None:
    app = _make_app(_transform=object())
    app.probe.selected_key_id = "old"
    app.probe.selected_slot_id = "top_01"
    redraw_calls: list[str] = []
    app._hit_test = lambda _x, _y: None
    app._redraw = lambda: redraw_calls.append("redraw")

    calibrator_app.KeymapCalibrator._on_click(app, SimpleNamespace(x=12, y=34))

    assert app.probe.selected_key_id is None
    assert app.probe.selected_slot_id is None
    assert app.lbl_status.text == "No key hit"
    assert redraw_calls == ["redraw"]


def test_on_click_selects_hit_key_and_reports_existing_mapping() -> None:
    app = _make_app(_transform=object(), keymap={"esc": ((0, 0), (0, 1))})
    redraw_calls: list[str] = []
    app._hit_test = lambda _x, _y: KeyDef("esc", "Esc", (0, 0, 10, 10))
    app._redraw = lambda: redraw_calls.append("redraw")

    calibrator_app.KeymapCalibrator._on_click(app, SimpleNamespace(x=12, y=34))

    assert app.probe.selected_key_id == "esc"
    assert app.probe.selected_slot_id == "esc"
    assert app.lbl_status.text == "Selected Esc (mapped ((0, 0), (0, 1)))"
    assert redraw_calls == ["redraw"]


def test_hit_test_returns_none_without_transform() -> None:
    app = _make_app(_transform=None)

    assert calibrator_app.KeymapCalibrator._hit_test(app, 10, 20) is None


def test_hit_test_uses_visible_keys_and_transform(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app(_transform=CanvasTransform(x0=1.0, y0=2.0, sx=3.0, sy=4.0))
    keys = [KeyDef("esc", "Esc", (0, 0, 10, 10))]
    result_key = KeyDef("f1", "F1", (10, 0, 10, 10))
    layout_calls: list[tuple[str, dict[str, dict[str, object]]]] = []
    hit_calls: list[dict[str, object]] = []

    def fake_get_layout_keys(
        physical_layout: str,
        *,
        legend_pack_id: str | None = None,
        slot_overrides: dict[str, dict[str, object]] | None = None,
    ) -> list[KeyDef]:
        layout_calls.append((physical_layout, legend_pack_id, dict(slot_overrides or {})))
        return keys

    def fake_hit_test(**kwargs: object) -> KeyDef:
        hit_calls.append(dict(kwargs))
        return result_key

    monkeypatch.setattr(calibrator_app, "get_layout_keys", fake_get_layout_keys)
    monkeypatch.setattr(calibrator_app, "hit_test", fake_hit_test)

    result = calibrator_app.KeymapCalibrator._hit_test(app, 55, 77)

    assert result is result_key
    assert layout_calls == [("ansi", None, {"macro": {"enabled": True}})]
    assert hit_calls == [
        {
            "transform": app._transform,
            "x": 55,
            "y": 77,
            "layout_tweaks": {"dx": 1.0},
            "per_key_layout_tweaks": {"esc": {"dx": 0.5}},
            "keys": keys,
            "image_size": BASE_IMAGE_SIZE,
        }
    ]


def test_selected_layout_legend_pack_ignores_invalid_or_cross_layout_values() -> None:
    assert (
        calibrator_app._selected_layout_legend_pack(SimpleNamespace(layout_legend_pack="auto"), physical_layout="iso")
        is None
    )
    assert (
        calibrator_app._selected_layout_legend_pack(
            SimpleNamespace(layout_legend_pack="iso-de-qwertz"),
            physical_layout="ansi",
        )
        is None
    )
    assert (
        calibrator_app._selected_layout_legend_pack(
            SimpleNamespace(layout_legend_pack="iso-de-qwertz"),
            physical_layout="iso",
        )
        == "iso-de-qwertz"
    )
