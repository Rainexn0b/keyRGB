from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.perkey.canvas as perkey_canvas
from src.gui.perkey.canvas import KeyboardCanvas


class _FakeVar:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


class _FakeEditor:
    def __init__(self) -> None:
        self.layout_tweaks: dict[str, object] = {"inset": 0.2}
        self.per_key_layout_tweaks: dict[str, dict[str, object]] = {"k1": {"dx": 1.0}}
        self.layout_slot_overrides = {"slot": True}
        self._physical_layout = "layout-a"
        self.overlay_scope = _FakeVar("key")
        self.selected_key_id: str | None = "k1"


class _FakeCanvasBase:
    def __init__(self) -> None:
        self.editor = _FakeEditor()
        self._deck_drawn_bbox: tuple[int, int, int, int] | None = None


class _FakeTkCanvas:
    def __init__(self, _parent=None, **_kwargs) -> None:
        self.bind_calls: list[tuple[str, object]] = []

    def bind(self, event: str, callback) -> None:
        self.bind_calls.append((event, callback))


def _key(
    key_id: str = "k1",
    *,
    rect=(10.0, 20.0, 30.0, 40.0),
    slot_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(key_id=key_id, rect=rect, label=key_id, slot_id=slot_id)


def test_init_wires_bindings_and_state(monkeypatch: pytest.MonkeyPatch) -> None:
    init_calls: list[tuple[object, dict[str, object]]] = []
    bind_calls: list[tuple[str, object]] = []
    load_calls: list[str] = []

    def fake_canvas_init(self, parent=None, **kwargs) -> None:
        init_calls.append((parent, dict(kwargs)))

    def fake_bind(self, event: str, callback) -> None:
        bind_calls.append((event, callback))

    monkeypatch.setattr(perkey_canvas.tk.Canvas, "__init__", fake_canvas_init)
    monkeypatch.setattr(perkey_canvas.tk.Canvas, "bind", fake_bind)
    monkeypatch.setattr(perkey_canvas, "DeckRenderCache", lambda: "cache")
    monkeypatch.setattr(KeyboardCanvas, "_load_deck_image", lambda self: load_calls.append("load"))

    editor = _FakeEditor()
    canvas = KeyboardCanvas("parent", editor, bg="black")

    assert init_calls == [("parent", {"bg": "black"})]
    assert canvas.editor is editor
    assert canvas._deck_render_cache == "cache"
    assert canvas._deck_img is None
    assert canvas._deck_img_tk is None
    assert canvas._deck_drawn_bbox is None
    assert canvas._resize_job is None
    assert canvas.key_rects == {}
    assert canvas.key_texts == {}
    assert isinstance(canvas._overlay_drag, perkey_canvas.OverlayDragController)
    assert [event for event, _ in bind_calls] == [
        "<Configure>",
        "<Button-1>",
        "<ButtonPress-1>",
        "<B1-Motion>",
        "<ButtonRelease-1>",
        "<Motion>",
        "<Leave>",
    ]
    assert bind_calls[0][1].__func__ is KeyboardCanvas._on_resize
    assert bind_calls[1][1].__func__ is KeyboardCanvas._on_click
    assert bind_calls[2][1] == canvas._overlay_drag.on_press
    assert bind_calls[3][1] == canvas._overlay_drag.on_drag
    assert bind_calls[4][1] == canvas._overlay_drag.on_release
    assert bind_calls[5][1].__func__ is KeyboardCanvas._on_motion
    assert bind_calls[6][1].__func__ is KeyboardCanvas._on_leave
    assert load_calls == ["load"]


def test_inset_pixels_uses_inset_bbox_left_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCanvasBase()
    calls: list[dict[str, float]] = []
    monkeypatch.setattr(
        perkey_canvas,
        "inset_bbox",
        lambda **kwargs: calls.append(kwargs) or (3.5, 4.0, 16.5, 18.0),
    )

    result = KeyboardCanvas._inset_pixels(fake, 20.0, 22.0, 0.1)

    assert result == 3.5
    assert calls == [{"x1": 0.0, "y1": 0.0, "x2": 20.0, "y2": 22.0, "inset_value": 0.1}]


def test_apply_global_and_per_key_tweak_delegate_to_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCanvasBase()
    global_calls: list[dict[str, object]] = []
    per_key_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        perkey_canvas,
        "apply_global_tweak",
        lambda **kwargs: global_calls.append(kwargs) or (1.0, 2.0, 3.0, 4.0),
    )
    monkeypatch.setattr(
        perkey_canvas,
        "apply_per_key_tweak",
        lambda **kwargs: per_key_calls.append(kwargs) or (5.0, 6.0, 7.0, 8.0, 0.25),
    )

    assert KeyboardCanvas._apply_global_tweak(fake, 10, 20, 30, 40) == (1.0, 2.0, 3.0, 4.0)
    assert KeyboardCanvas._apply_per_key_tweak(fake, "k1", 11, 22, 33, 44) == (5.0, 6.0, 7.0, 8.0, 0.25)
    assert global_calls == [
        {
            "rect": (10.0, 20.0, 30.0, 40.0),
            "layout_tweaks": fake.editor.layout_tweaks,
            "image_size": perkey_canvas.BASE_IMAGE_SIZE,
        }
    ]
    assert per_key_calls == [
        {
            "key_id": "k1",
            "slot_id": None,
            "rect": (11.0, 22.0, 33.0, 44.0),
            "per_key_layout_tweaks": fake.editor.per_key_layout_tweaks,
            "inset_default": 0.2,
        }
    ]


def test_key_rect_canvas_and_transform_handle_missing_bbox(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCanvasBase()
    fake._canvas_transform = lambda: None

    assert KeyboardCanvas._key_rect_canvas(fake, _key()) is None
    assert KeyboardCanvas._canvas_transform(fake) is None

    fake._deck_drawn_bbox = (1, 2, 300, 150)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        perkey_canvas,
        "transform_from_drawn_bbox",
        lambda **kwargs: calls.append(kwargs) or "transform",
    )
    assert KeyboardCanvas._canvas_transform(fake) == "transform"
    assert calls == [{"x0": 1, "y0": 2, "draw_w": 300, "draw_h": 150, "image_size": perkey_canvas.BASE_IMAGE_SIZE}]

    fake2 = _FakeCanvasBase()
    fake2._canvas_transform = lambda: "tx"
    calls2: list[dict[str, object]] = []
    monkeypatch.setattr(
        perkey_canvas,
        "key_canvas_rect",
        lambda **kwargs: calls2.append(kwargs) or (4.0, 5.0, 14.0, 15.0, 0.3),
    )
    assert KeyboardCanvas._key_rect_canvas(fake2, _key()) == (4.0, 5.0, 14.0, 15.0, 0.3)
    assert calls2[0]["transform"] == "tx"


def test_keydef_lookup_prefers_visible_layout_key_then_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCanvasBase()
    visible = [_key("visible")]
    monkeypatch.setattr(perkey_canvas, "get_layout_keys", lambda *_args, **_kwargs: visible)

    assert KeyboardCanvas._keydef_by_id(fake, "visible") is visible[0]

    fallback_key = _key("fallback")
    monkeypatch.setattr(perkey_canvas, "KEYDEF_BY_ID", {"fallback": fallback_key})
    assert KeyboardCanvas._keydef_by_id(fake, "fallback") is fallback_key
    assert KeyboardCanvas._keydef_by_id(fake, "missing") is None


def test_resize_and_point_helpers_handle_missing_bboxes_and_success() -> None:
    fake = _FakeCanvasBase()
    key_obj = _key("k1")
    fake._keydef_by_id = lambda key_id: key_obj if key_id == "k1" else None
    fake._key_bbox_canvas = lambda key: (1.0, 2.0, 11.0, 22.0) if key is key_obj else None

    assert KeyboardCanvas._resize_edges_for_point(fake, "missing", 3.0, 4.0) == ""
    assert KeyboardCanvas._point_in_key_bbox(fake, "missing", 3.0, 4.0) is False
    assert KeyboardCanvas._point_near_key_bbox(fake, "missing", 3.0, 4.0, pad=5.0) is False

    assert KeyboardCanvas._resize_edges_for_point(fake, "k1", 1.0, 2.0) == "lt"
    assert KeyboardCanvas._cursor_for_edges(fake, "rb") == "top_left_corner"
    assert KeyboardCanvas._point_in_key_bbox(fake, "k1", 3.0, 4.0) is True
    assert KeyboardCanvas._point_near_key_bbox(fake, "k1", -2.0, 0.0, pad=5.0) is True


def test_key_rect_base_bbox_and_overlay_drag_geometry() -> None:
    fake = _FakeCanvasBase()
    key_obj = _key("k1", rect=(10.0, 20.0, 30.0, 40.0))
    key_obj.slot_id = "slot_k1"
    fake._keydef_by_id = lambda key_id: key_obj if key_id == "k1" else None
    fake._apply_global_tweak = lambda x, y, w, h: (x + 1.0, y + 2.0, w + 3.0, h + 4.0)
    fake._apply_per_key_tweak = lambda key_id, x, y, w, h, slot_id=None: (x + 10.0, y + 20.0, w + 30.0, h + 40.0, 0.5)
    fake._key_rect_canvas = lambda key: (2.0, 4.0, 22.0, 34.0, 0.25)
    fake._inset_pixels = lambda w, h, inset: 3.0
    fake._key_rect_base_after_global = KeyboardCanvas._key_rect_base_after_global.__get__(fake, _FakeCanvasBase)

    assert KeyboardCanvas._key_rect_base_after_global(fake, "k1") == (11.0, 22.0, 33.0, 44.0)
    assert KeyboardCanvas._key_rect_base_after_global(fake, "missing") is None
    assert KeyboardCanvas._key_bbox_canvas(fake, key_obj) == (5.0, 7.0, 19.0, 31.0)
    assert KeyboardCanvas._overlay_drag_geometry(fake, "k1") == (11.0, 22.0, 33.0, 44.0, 21.0, 84.0, 42.0, 126.0)
    assert KeyboardCanvas._overlay_drag_geometry(fake, "missing") is None


def test_hit_test_key_id_returns_first_matching_visible_key(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCanvasBase()
    fake._canvas_transform = lambda: "tx"
    fake.editor.layout_tweaks = {"a": 1}
    fake.editor.per_key_layout_tweaks = {"b": 2}
    visible = [_key("k1", slot_id="slot_k1"), _key("k2", slot_id="slot_k2")]
    monkeypatch.setattr(perkey_canvas, "get_layout_keys", lambda *_args, **_kwargs: visible)

    hit_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        perkey_canvas,
        "key_canvas_hit_rects",
        lambda **kwargs: (
            hit_calls.append(kwargs)
            or ([(0.0, 0.0, 5.0, 5.0)] if kwargs["key"].key_id == "k1" else [(10.0, 10.0, 20.0, 20.0)])
        ),
    )

    assert KeyboardCanvas._hit_test_slot_id(fake, 3.0, 4.0) == "slot_k1"
    assert KeyboardCanvas._hit_test_key_id(fake, 3.0, 4.0) == "k1"
    assert KeyboardCanvas._hit_test_slot_id(fake, 50.0, 50.0) is None
    assert KeyboardCanvas._hit_test_key_id(fake, 50.0, 50.0) is None
    assert len(hit_calls) >= 2

    fake._canvas_transform = lambda: None
    assert KeyboardCanvas._hit_test_slot_id(fake, 1.0, 1.0) is None
    assert KeyboardCanvas._hit_test_key_id(fake, 1.0, 1.0) is None


def test_overlay_press_mode_distinguishes_resize_move_and_miss() -> None:
    fake = _FakeCanvasBase()
    fake._keydef_by_id = lambda key_id: _key("k1", slot_id="slot_k1") if key_id == "k1" else None
    fake._resize_edges_for_point = lambda slot_id, cx, cy: "rb"
    fake._point_near_key_bbox = lambda slot_id, cx, cy, pad: True
    fake._hit_test_slot_id = lambda cx, cy: "slot_k1"

    assert KeyboardCanvas._overlay_press_mode(fake, selected_slot_id="slot_k1", cx=4.0, cy=5.0) == ("resize", "rb")
    assert KeyboardCanvas._overlay_press_mode(fake, selected_key_id="k1", cx=4.0, cy=5.0) == ("resize", "rb")

    fake._point_near_key_bbox = lambda slot_id, cx, cy, pad: False
    assert KeyboardCanvas._overlay_press_mode(fake, selected_slot_id="slot_k1", cx=4.0, cy=5.0) is None

    fake._resize_edges_for_point = lambda slot_id, cx, cy: ""
    fake._hit_test_slot_id = lambda cx, cy: "slot_k1"
    assert KeyboardCanvas._overlay_press_mode(fake, selected_slot_id="slot_k1", cx=4.0, cy=5.0) == ("move", "")

    fake._hit_test_slot_id = lambda cx, cy: "other"
    assert KeyboardCanvas._overlay_press_mode(fake, selected_slot_id="slot_k1", cx=4.0, cy=5.0) is None
    assert KeyboardCanvas._overlay_press_mode(fake, selected_key_id="", cx=4.0, cy=5.0) is None
