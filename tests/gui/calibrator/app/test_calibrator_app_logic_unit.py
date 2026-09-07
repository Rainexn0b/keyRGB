from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from keyrgb.gui.calibrator import app as calibrator_app
from keyrgb.gui.calibrator.helpers.probe import CalibrationProbeState


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


def test_load_deck_image_for_calibrator_loads_builtin_and_clears_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    image = object()
    calls: list[tuple[str, str | None]] = []

    def fake_load_backdrop_image(profile_name: str, *, backdrop_mode: str | None = None) -> object:
        calls.append((profile_name, backdrop_mode))
        return image

    monkeypatch.setattr(calibrator_app, "load_backdrop_image", fake_load_backdrop_image)
    monkeypatch.setattr(calibrator_app.profiles, "load_backdrop_mode", lambda _name: "builtin")

    calibrator_app.KeymapCalibrator._load_deck_image(app)

    assert calls == [("gaming", "builtin")]
    assert app._deck_pil is image
    assert app._deck_render_cache.clear_calls == 1


def test_load_deck_image_for_calibrator_treats_none_mode_as_builtin(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    image = object()
    calls: list[tuple[str, str | None]] = []

    def fake_load_backdrop_image(profile_name: str, *, backdrop_mode: str | None = None) -> object:
        calls.append((profile_name, backdrop_mode))
        return image

    monkeypatch.setattr(calibrator_app, "load_backdrop_image", fake_load_backdrop_image)
    monkeypatch.setattr(calibrator_app.profiles, "load_backdrop_mode", lambda _name: "none")

    calibrator_app.KeymapCalibrator._load_deck_image(app)

    assert calls == [("gaming", "builtin")]
    assert app._deck_pil is image


def test_load_deck_image_falls_back_to_builtin_when_custom_image_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    builtin_image = object()
    calls: list[tuple[str, str | None]] = []

    def fake_load_backdrop_image(profile_name: str, *, backdrop_mode: str | None = None) -> object | None:
        calls.append((profile_name, backdrop_mode))
        if backdrop_mode == "custom":
            return None
        return builtin_image

    monkeypatch.setattr(calibrator_app, "load_backdrop_image", fake_load_backdrop_image)
    monkeypatch.setattr(calibrator_app.profiles, "load_backdrop_mode", lambda _name: "custom")

    calibrator_app.KeymapCalibrator._load_deck_image(app)

    assert calls == [("gaming", "custom"), ("gaming", "builtin")]
    assert app._deck_pil is builtin_image
    assert app._deck_render_cache.clear_calls == 1


def test_on_show_backdrop_changed_loads_image_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    image = object()
    app._show_backdrop_var = type("Var", (), {"get": lambda self: True})()
    app._redraw = lambda: None

    def fake_load_backdrop_image(profile_name: str, *, backdrop_mode: str | None = None) -> object:
        return image

    monkeypatch.setattr(calibrator_app, "load_backdrop_image", fake_load_backdrop_image)
    monkeypatch.setattr(calibrator_app.profiles, "load_backdrop_mode", lambda _name: "builtin")

    calibrator_app.KeymapCalibrator._on_show_backdrop_changed(app)

    assert app._deck_pil is image


def test_on_show_backdrop_changed_clears_image_when_disabled() -> None:
    app = _make_app()
    app._deck_pil = object()
    app._show_backdrop_var = type("Var", (), {"get": lambda self: False})()
    redraw_calls: list[str] = []
    app._redraw = lambda: redraw_calls.append("redraw")

    calibrator_app.KeymapCalibrator._on_show_backdrop_changed(app)

    assert app._deck_pil is None
    assert app._deck_render_cache.clear_calls == 1
    assert redraw_calls == ["redraw"]


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
