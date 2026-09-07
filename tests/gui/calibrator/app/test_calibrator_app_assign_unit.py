from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from keyrgb.core.resources.layout import BASE_IMAGE_SIZE, KeyDef
from keyrgb.core.resources.layouts import slot_id_for_key_id
from keyrgb.gui.calibrator import app as calibrator_app
from keyrgb.gui.calibrator.helpers.probe import CalibrationProbeState
from keyrgb.gui.reference.overlay_geometry import CanvasTransform


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
