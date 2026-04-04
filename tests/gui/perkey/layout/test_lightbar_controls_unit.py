from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.perkey.lightbar_controls as lightbar_controls
from src.core.resources.defaults import get_default_lightbar_overlay


class _FakeVar:
    def __init__(self, value=0.0):
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value


class _FakeCanvas:
    def __init__(self, *, width: float = 180.0, height: float = 88.0):
        self.width = width
        self.height = height
        self.deleted = []
        self.rectangles = []
        self.redraw_calls = 0

    def winfo_width(self) -> float:
        return self.width

    def winfo_height(self) -> float:
        return self.height

    def delete(self, tag: str) -> None:
        self.deleted.append(tag)

    def create_rectangle(self, *args, **kwargs) -> None:
        self.rectangles.append((args, kwargs))

    def redraw(self) -> None:
        self.redraw_calls += 1


class _BrokenRedrawCanvas(_FakeCanvas):
    def __init__(self, exc: Exception):
        super().__init__()
        self.exc = exc

    def redraw(self) -> None:
        raise self.exc


class _BrokenSizeCanvas(_FakeCanvas):
    def __init__(self, exc: Exception):
        super().__init__()
        self.exc = exc

    def winfo_width(self) -> float:
        raise self.exc


def _controls(payload: dict[str, bool | float] | None = None):
    editor = SimpleNamespace(
        lightbar_overlay=dict(payload or get_default_lightbar_overlay()),
        profile_name="gaming",
        status_label=SimpleNamespace(config=lambda **_kwargs: None),
        canvas=_FakeCanvas(),
    )
    controls = SimpleNamespace(
        editor=editor,
        visible_var=_FakeVar(True),
        length_var=_FakeVar(0.72),
        thickness_var=_FakeVar(0.12),
        dx_var=_FakeVar(0.0),
        dy_var=_FakeVar(0.0),
        inset_var=_FakeVar(0.04),
        preview_canvas=_FakeCanvas(),
    )
    controls.redraw_preview = lambda: lightbar_controls.LightbarControls.redraw_preview(controls)
    controls.apply_from_vars = lambda: lightbar_controls.LightbarControls.apply_from_vars(controls)
    controls.sync_vars_from_editor = lambda: lightbar_controls.LightbarControls.sync_vars_from_editor(controls)
    controls._redraw_editor_canvas = lambda: lightbar_controls.LightbarControls._redraw_editor_canvas(controls)
    return controls


controls = None


def test_sync_vars_from_editor_loads_payload_and_draws_preview() -> None:
    global controls
    controls = _controls({"visible": False, "length": 0.9, "thickness": 0.2, "dx": 0.1, "dy": -0.1, "inset": 0.05})

    lightbar_controls.LightbarControls.sync_vars_from_editor(controls)

    assert controls.visible_var.get() is False
    assert controls.length_var.get() == pytest.approx(0.9)
    assert controls.thickness_var.get() == pytest.approx(0.2)
    assert controls.dx_var.get() == pytest.approx(0.1)
    assert controls.dy_var.get() == pytest.approx(-0.1)
    assert controls.inset_var.get() == pytest.approx(0.05)
    assert controls.preview_canvas.deleted == ["all"]


def test_apply_from_vars_clamps_and_updates_editor_payload() -> None:
    global controls
    controls = _controls()
    controls.visible_var.set(False)
    controls.length_var.set(99.0)
    controls.thickness_var.set(-1.0)
    controls.dx_var.set(2.0)
    controls.dy_var.set(-2.0)
    controls.inset_var.set(1.0)

    payload = lightbar_controls.LightbarControls.apply_from_vars(controls)

    assert payload == {
        "visible": False,
        "length": pytest.approx(1.0),
        "thickness": pytest.approx(0.04),
        "dx": pytest.approx(0.5),
        "dy": pytest.approx(-0.5),
        "inset": pytest.approx(0.25),
    }
    assert controls.editor.lightbar_overlay == payload
    assert controls.editor.canvas.redraw_calls == 1


def test_save_tweaks_persists_profile_overlay(monkeypatch) -> None:
    global controls
    controls = _controls()

    saved = {}
    monkeypatch.setattr(
        lightbar_controls.profiles,
        "save_lightbar_overlay",
        lambda payload, name: saved.setdefault("call", (payload, name)) or payload,
    )

    lightbar_controls.LightbarControls.save_tweaks(controls)

    assert saved["call"][1] == "gaming"
    assert isinstance(saved["call"][0], dict)


def test_reset_tweaks_restores_defaults() -> None:
    global controls
    controls = _controls({"visible": False, "length": 0.9, "thickness": 0.2, "dx": 0.1, "dy": 0.1, "inset": 0.1})

    lightbar_controls.LightbarControls.reset_tweaks(controls)

    assert controls.editor.lightbar_overlay == get_default_lightbar_overlay()
    assert controls.editor.canvas.redraw_calls == 1


def test_apply_from_vars_tolerates_broken_editor_canvas_redraw() -> None:
    local_controls = _controls()
    local_controls.editor.canvas = _BrokenRedrawCanvas(RuntimeError("boom"))

    payload = lightbar_controls.LightbarControls.apply_from_vars(local_controls)

    assert local_controls.editor.lightbar_overlay == payload


def test_reset_tweaks_tolerates_missing_editor_canvas_redraw() -> None:
    local_controls = _controls({"visible": False, "length": 0.9, "thickness": 0.2, "dx": 0.1, "dy": 0.1, "inset": 0.1})
    local_controls.editor.canvas = object()

    lightbar_controls.LightbarControls.reset_tweaks(local_controls)

    assert local_controls.editor.lightbar_overlay == get_default_lightbar_overlay()


def test_redraw_preview_falls_back_to_default_size_on_size_lookup_error() -> None:
    local_controls = _controls()
    local_controls.preview_canvas = _BrokenSizeCanvas(ValueError("bad width"))

    lightbar_controls.LightbarControls.redraw_preview(local_controls)

    assert local_controls.preview_canvas.deleted == ["all"]
    assert local_controls.preview_canvas.rectangles[0][0] == (8, 8, 172.0, 80.0)
