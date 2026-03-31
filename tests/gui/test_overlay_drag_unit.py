from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.gui.perkey.overlay.drag import OverlayDragController


class _FakeVar:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


class _FakeEditor:
    def __init__(self, *, scope: str = "key", selected_key_id: str | None = "k1") -> None:
        self.overlay_scope = _FakeVar(scope)
        self.selected_key_id = selected_key_id
        self.per_key_layout_tweaks: dict[str, dict[str, float]] = {}
        self.layout_tweaks: dict[str, float] = {}
        self.sync_calls = 0

    def sync_overlay_vars(self) -> None:
        self.sync_calls += 1


class _FakeCanvas:
    def __init__(self, *, scope: str = "key", selected_key_id: str | None = "k1") -> None:
        self.editor = _FakeEditor(scope=scope, selected_key_id=selected_key_id)
        self.transform = SimpleNamespace(sx=2.0, sy=4.0)
        self.press_result = None
        self.geometry_result = None
        self.redraw_calls = 0

    def _canvas_transform(self):
        return self.transform

    def _overlay_press_mode(self, *, selected_key_id: str, cx: float, cy: float, pad: float):
        self.last_press = (selected_key_id, cx, cy, pad)
        return self.press_result

    def _overlay_drag_geometry(self, key_id: str):
        self.last_geometry = key_id
        return self.geometry_result

    def redraw(self) -> None:
        self.redraw_calls += 1


def _event(*, x: float = 10, y: float = 20) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


def test_on_press_clears_context_when_scope_or_selection_is_invalid() -> None:
    canvas = _FakeCanvas(scope="global")
    controller = OverlayDragController(canvas)

    controller.on_press(_event())
    assert controller._ctx is None

    canvas2 = _FakeCanvas(scope="key", selected_key_id=None)
    controller2 = OverlayDragController(canvas2)
    controller2.on_press(_event())
    assert controller2._ctx is None


def test_on_press_clears_context_when_press_mode_or_geometry_missing() -> None:
    canvas = _FakeCanvas()
    controller = OverlayDragController(canvas)

    controller.on_press(_event())
    assert controller._ctx is None

    canvas.press_result = ("move", "")
    controller.on_press(_event())
    assert controller._ctx is None


def test_on_press_builds_context_from_selected_key_geometry_and_tweaks() -> None:
    canvas = _FakeCanvas()
    canvas.editor.per_key_layout_tweaks = {"k1": {"dx": 1.5, "dy": -2.0, "sx": 1.2, "sy": 0.8}}
    canvas.press_result = ("resize", "rb")
    canvas.geometry_result = (10.0, 20.0, 30.0, 40.0, 11.0, 41.0, 21.0, 61.0)
    controller = OverlayDragController(canvas)

    controller.on_press(_event(x=14, y=18))

    assert controller._ctx is not None
    assert controller._ctx.kid == "k1"
    assert controller._ctx.mode == "resize"
    assert controller._ctx.edges == "rb"
    assert controller._ctx.x == 14.0
    assert controller._ctx.y == 18.0
    assert controller._ctx.dx == 1.5
    assert controller._ctx.dy == -2.0
    assert controller._ctx.sx == 1.2
    assert controller._ctx.sy == 0.8


def test_on_drag_noops_without_context_or_transform() -> None:
    canvas = _FakeCanvas()
    controller = OverlayDragController(canvas)

    controller.on_drag(_event())
    assert canvas.redraw_calls == 0

    canvas.press_result = ("move", "")
    canvas.geometry_result = (0.0, 0.0, 10.0, 10.0, 0.0, 10.0, 0.0, 10.0)
    controller.on_press(_event())
    canvas.transform = None

    controller.on_drag(_event(x=20, y=40))
    assert canvas.redraw_calls == 0


def test_on_drag_updates_move_offsets_and_preserves_inset_default() -> None:
    canvas = _FakeCanvas()
    canvas.editor.layout_tweaks = {"inset": 0.2}
    canvas.press_result = ("move", "")
    canvas.geometry_result = (10.0, 20.0, 30.0, 40.0, 10.0, 40.0, 20.0, 60.0)
    controller = OverlayDragController(canvas)
    controller.on_press(_event(x=8, y=12))

    controller.on_drag(_event(x=18, y=28))

    assert canvas.editor.per_key_layout_tweaks["k1"] == {
        "inset": 0.2,
        "dx": 5.0,
        "dy": 4.0,
    }
    assert canvas.editor.sync_calls == 1
    assert canvas.redraw_calls == 1


def test_on_drag_updates_resize_geometry_with_clamps() -> None:
    canvas = _FakeCanvas()
    canvas.press_result = ("resize", "lt")
    canvas.geometry_result = (10.0, 10.0, 40.0, 20.0, 10.0, 50.0, 10.0, 30.0)
    controller = OverlayDragController(canvas)
    controller.on_press(_event(x=20, y=20))

    controller.on_drag(_event(x=220, y=220))

    kt = canvas.editor.per_key_layout_tweaks["k1"]
    assert kt["inset"] == 0.06
    assert kt["sx"] == pytest.approx(0.3)
    assert kt["sy"] == pytest.approx(0.3)
    assert kt["dx"] == pytest.approx(85.0)
    assert kt["dy"] == pytest.approx(43.0)
    assert canvas.editor.sync_calls == 1
    assert canvas.redraw_calls == 1


def test_on_release_clears_context() -> None:
    canvas = _FakeCanvas()
    canvas.press_result = ("move", "")
    canvas.geometry_result = (0.0, 0.0, 10.0, 10.0, 0.0, 10.0, 0.0, 10.0)
    controller = OverlayDragController(canvas)
    controller.on_press(_event())
    assert controller._ctx is not None

    controller.on_release(_event())

    assert controller._ctx is None