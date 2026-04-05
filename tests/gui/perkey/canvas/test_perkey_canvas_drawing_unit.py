from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from PIL import Image

import src.gui.perkey.canvas_impl._canvas_drawing as canvas_drawing
from src.gui.perkey.canvas_impl._canvas_drawing import (
    _KeyboardCanvasDrawingMixin,
    _shape_polygon_points,
)


@dataclass(frozen=True)
class _Style:
    fill: str
    stipple: str | None
    outline: str
    width: int
    dash: tuple[int, ...]
    text_fill: str


@dataclass(frozen=True)
class _Key:
    key_id: str
    label: str
    slot_id: str | None = None


class _FakeVar:
    def __init__(self, value: object, *, exc: Exception | None = None) -> None:
        self.value = value
        self.exc = exc

    def get(self) -> object:
        if self.exc is not None:
            raise self.exc
        return self.value


class _FakeDeckRenderCache:
    def __init__(self) -> None:
        self.clear_calls = 0
        self.get_calls: list[dict[str, object]] = []
        self.result: object = "photo"
        self.error: Exception | None = None

    def clear(self) -> None:
        self.clear_calls += 1

    def get_or_create(self, **kwargs: object) -> object:
        self.get_calls.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        return self.result


class _FakeEditor:
    def __init__(self) -> None:
        self.profile_name: object = "profile-a"
        self.layout_slot_overrides: dict[str, object] | None = None
        self.layout_tweaks: dict[str, object] = {}
        self.per_key_layout_tweaks: dict[str, object] = {}
        self.has_lightbar_device = False
        self.lightbar_overlay: dict[str, object] = {"visible": True}
        self._physical_layout = "auto"
        self.selected_key_id: str | None = None
        self.selected_slot_id: str | None = None
        self.keymap: dict[str, tuple[int, int]] = {}
        self.colors: dict[tuple[int, int], tuple[int, int, int]] = {}
        self.backdrop_transparency = _FakeVar("0")
        self.clicked_keys: list[str] = []

    def on_key_clicked(self, key_id: str) -> None:
        self.clicked_keys.append(str(key_id))

    def on_slot_clicked(self, slot_id: str) -> None:
        self.clicked_keys.append(str(slot_id))


class _FakeCanvas(_KeyboardCanvasDrawingMixin):
    def __init__(self) -> None:
        self.editor = _FakeEditor()
        self._deck_render_cache = _FakeDeckRenderCache()
        self._deck_img = None
        self._deck_img_tk = None
        self._deck_drawn_bbox = None
        self.key_rects: dict[str, int] = {}
        self.key_texts: dict[str, int] = {}
        self.deleted_tags: list[str] = []
        self.rectangles: list[dict[str, object]] = []
        self.polygons: list[dict[str, object]] = []
        self.texts: list[dict[str, object]] = []
        self.images: list[dict[str, object]] = []
        self.itemconfig_calls: list[tuple[int, dict[str, object]]] = []
        self.tag_bind_calls: list[tuple[str, str, object]] = []
        self._transform = None
        self._inset_result = 0.0
        self.width = 400
        self.height = 300
        self._next_id = 1

    def delete(self, tag: str) -> None:
        self.deleted_tags.append(tag)

    def create_rectangle(self, x1: float, y1: float, x2: float, y2: float, **kwargs: object) -> int:
        obj_id = self._next_id
        self._next_id += 1
        self.rectangles.append({"coords": (x1, y1, x2, y2), **dict(kwargs)})
        return obj_id

    def create_polygon(self, points: list[float], **kwargs: object) -> int:
        obj_id = self._next_id
        self._next_id += 1
        self.polygons.append({"points": list(points), **dict(kwargs)})
        return obj_id

    def create_text(self, x: float, y: float, **kwargs: object) -> int:
        obj_id = self._next_id
        self._next_id += 1
        self.texts.append({"coords": (x, y), **dict(kwargs)})
        return obj_id

    def create_image(self, x: float, y: float, **kwargs: object) -> int:
        obj_id = self._next_id
        self._next_id += 1
        self.images.append({"coords": (x, y), **dict(kwargs)})
        return obj_id

    def itemconfig(self, item_id: int, **kwargs: object) -> None:
        self.itemconfig_calls.append((item_id, dict(kwargs)))

    def tag_bind(self, tag: str, event: str, callback) -> None:
        self.tag_bind_calls.append((tag, event, callback))

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height

    def _canvas_transform(self):
        return self._transform

    def _inset_pixels(self, _width: float, _height: float, _inset_value: float) -> float:
        return self._inset_result


class _FakeFont:
    def __init__(self, font: tuple[str, int]) -> None:
        self.size = int(font[1])

    def configure(self, *, size: int) -> None:
        self.size = int(size)

    def measure(self, text: str) -> int:
        if text == "…":
            return 1
        return len(text) * 2


@pytest.mark.parametrize(
    ("rects", "expected"),
    [
        ([(1.0, 2.0, 3.0, 4.0)], [1.0, 2.0, 3.0, 2.0, 3.0, 4.0, 1.0, 4.0]),
        (
            [(1.0, 5.0, 4.0, 8.0), (0.0, 0.0, 3.0, 3.0), (2.0, 1.0, 6.0, 9.0)],
            [0.0, 0.0, 6.0, 0.0, 6.0, 9.0, 0.0, 9.0],
        ),
    ],
)
def test_shape_polygon_points_handles_non_stepped_shapes(
    rects: list[tuple[float, float, float, float]],
    expected: list[float],
) -> None:
    assert _shape_polygon_points(rects) == expected


def test_shape_polygon_points_builds_stepped_polygon_for_two_rectangles() -> None:
    result = _shape_polygon_points([(5.0, 5.0, 9.0, 8.0), (1.0, 1.0, 7.0, 5.0)])

    assert result == [1.0, 1.0, 7.0, 1.0, 7.0, 5.0, 9.0, 5.0, 9.0, 8.0, 5.0, 8.0, 5.0, 5.0, 1.0, 5.0]


def test_load_deck_image_uses_string_profile_and_clears_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    image = Image.new("RGBA", (4, 4))
    calls: list[object] = []

    def fake_load_backdrop_image(profile_name: str) -> Image.Image:
        calls.append(profile_name)
        return image

    monkeypatch.setattr(canvas_drawing, "load_backdrop_image", fake_load_backdrop_image)

    canvas._load_deck_image()

    assert calls == ["profile-a"]
    assert canvas._deck_img is image
    assert canvas._deck_render_cache.clear_calls == 1


def test_load_deck_image_can_store_no_backdrop(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    monkeypatch.setattr(canvas_drawing, "load_backdrop_image", lambda _profile_name: None)

    canvas._load_deck_image()

    assert canvas._deck_img is None
    assert canvas._deck_render_cache.clear_calls == 1


def test_load_deck_image_passes_none_for_non_string_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas.editor.profile_name = 123
    calls: list[object] = []
    monkeypatch.setattr(canvas_drawing, "load_backdrop_image", lambda profile_name: calls.append(profile_name))

    canvas._load_deck_image()

    assert calls == []
    assert canvas._deck_render_cache.clear_calls == 1


def test_reload_backdrop_image_reloads_then_redraws() -> None:
    canvas = _FakeCanvas()
    calls: list[str] = []
    canvas._load_deck_image = lambda: calls.append("load")
    canvas.redraw = lambda: calls.append("redraw")

    canvas.reload_backdrop_image()

    assert calls == ["load", "redraw"]


def test_redraw_returns_early_without_transform_after_resetting_canvas() -> None:
    canvas = _FakeCanvas()
    calls: list[str] = []
    canvas._draw_deck_background = lambda: calls.append("bg")

    canvas.redraw()

    assert canvas.deleted_tags == ["all"]
    assert calls == ["bg"]
    assert canvas.key_rects == {}
    assert canvas.key_texts == {}


def test_redraw_draws_lightbar_overlay_before_keys_when_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas._transform = SimpleNamespace(to_canvas=lambda rect: (50.0, 60.0, 150.0, 80.0))
    canvas.editor.has_lightbar_device = True
    canvas.editor.lightbar_overlay = {"visible": True}

    monkeypatch.setattr(canvas_drawing, "lightbar_rect_for_size", lambda **_kwargs: (10.0, 20.0, 40.0, 30.0))
    monkeypatch.setattr(canvas_drawing, "get_layout_keys", lambda *_args, **_kwargs: [_Key("k1", "Esc")])
    monkeypatch.setattr(canvas_drawing, "key_canvas_rect", lambda **_kwargs: (1.0, 2.0, 21.0, 12.0, 0.0))
    monkeypatch.setattr(canvas_drawing, "key_canvas_hit_rects", lambda **_kwargs: [(1.0, 2.0, 21.0, 12.0)])
    monkeypatch.setattr(
        canvas_drawing,
        "key_draw_style",
        lambda **_kwargs: _Style("#010203", "gray50", "#ffffff", 2, (), "#eeeeee"),
    )
    monkeypatch.setattr(canvas_drawing.tkfont, "Font", _FakeFont)
    canvas._draw_deck_background = lambda: None

    canvas.redraw()

    assert canvas.rectangles[0] == {
        "coords": (50.0, 60.0, 150.0, 80.0),
        "fill": "#f28c28",
        "stipple": "gray50",
        "outline": "#f7c56f",
        "width": 2,
        "tags": ("lightbar_overlay",),
    }
    assert canvas.rectangles[1]["tags"] == ("pslot_k1", "pkey_k1", "pkey")


def test_draw_lightbar_overlay_is_noop_when_hidden_or_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas._transform = SimpleNamespace(to_canvas=lambda rect: rect)

    canvas._draw_lightbar_overlay()
    assert canvas.rectangles == []

    canvas.editor.has_lightbar_device = True
    monkeypatch.setattr(canvas_drawing, "lightbar_rect_for_size", lambda **_kwargs: None)
    canvas._draw_lightbar_overlay()
    assert canvas.rectangles == []


def test_redraw_creates_rectangle_text_and_tag_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas._transform = object()
    canvas.editor.selected_key_id = "k1"
    canvas.editor.selected_slot_id = "k1"
    canvas.editor.keymap = {"k1": (0, 0)}
    canvas.editor.colors = {(0, 0): (10, 20, 30)}

    monkeypatch.setattr(canvas_drawing, "get_layout_keys", lambda *_args, **_kwargs: [_Key("k1", "Esc")])
    monkeypatch.setattr(canvas_drawing, "key_canvas_rect", lambda **_kwargs: (1.0, 2.0, 21.0, 12.0, 0.0))
    monkeypatch.setattr(canvas_drawing, "key_canvas_hit_rects", lambda **_kwargs: [(1.0, 2.0, 21.0, 12.0)])
    monkeypatch.setattr(
        canvas_drawing,
        "key_draw_style",
        lambda **_kwargs: _Style("#010203", "gray50", "#ffffff", 2, (), "#eeeeee"),
    )
    monkeypatch.setattr(canvas_drawing.tkfont, "Font", _FakeFont)
    canvas._draw_deck_background = lambda: None

    canvas.redraw()

    assert len(canvas.rectangles) == 1
    assert len(canvas.texts) == 1
    assert canvas.rectangles[0]["tags"] == ("pslot_k1", "pkey_k1", "pkey")
    assert canvas.texts[0]["text"] == "Esc"
    assert "k1" in canvas.key_rects
    assert "k1" in canvas.key_texts
    assert canvas.tag_bind_calls and canvas.tag_bind_calls[0][0] == "pslot_k1"

    callback = canvas.tag_bind_calls[0][2]
    callback(None)
    assert canvas.editor.clicked_keys == ["k1"]


def test_redraw_uses_polygon_path_and_truncates_wide_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas._transform = object()
    monkeypatch.setattr(canvas_drawing, "get_layout_keys", lambda *_args, **_kwargs: [_Key("k2", "LongName")])
    monkeypatch.setattr(canvas_drawing, "key_canvas_rect", lambda **_kwargs: (0.0, 0.0, 12.0, 12.0, 0.0))
    monkeypatch.setattr(
        canvas_drawing,
        "key_canvas_hit_rects",
        lambda **_kwargs: [(0.0, 0.0, 8.0, 6.0), (4.0, 6.0, 12.0, 12.0)],
    )
    monkeypatch.setattr(
        canvas_drawing,
        "key_draw_style",
        lambda **_kwargs: _Style("#111111", None, "#222222", 1, (2, 1), "#fefefe"),
    )
    monkeypatch.setattr(canvas_drawing.tkfont, "Font", _FakeFont)
    canvas._draw_deck_background = lambda: None

    canvas.redraw()

    assert len(canvas.polygons) == 1
    assert canvas.texts[0]["text"].endswith("…")
    assert canvas.polygons[0]["joinstyle"] == "miter"


def test_redraw_survives_font_measure_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas._transform = object()

    class _BrokenFont:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def measure(self, _text: str) -> int:
            raise RuntimeError("boom")

    monkeypatch.setattr(canvas_drawing, "get_layout_keys", lambda *_args, **_kwargs: [_Key("k3", "Label")])
    monkeypatch.setattr(canvas_drawing, "key_canvas_rect", lambda **_kwargs: (0.0, 0.0, 20.0, 10.0, 0.0))
    monkeypatch.setattr(canvas_drawing, "key_canvas_hit_rects", lambda **_kwargs: [(0.0, 0.0, 20.0, 10.0)])
    monkeypatch.setattr(
        canvas_drawing,
        "key_draw_style",
        lambda **_kwargs: _Style("#111111", None, "#222222", 1, (), "#fefefe"),
    )
    monkeypatch.setattr(canvas_drawing.tkfont, "Font", _BrokenFont)
    canvas._draw_deck_background = lambda: None

    canvas.redraw()

    assert canvas.texts[0]["text"] == "Label"


def test_draw_deck_background_is_noop_without_image(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    monkeypatch.setattr(canvas_drawing, "calc_centered_drawn_bbox", lambda **_kwargs: (5, 6, 40, 20, 2.0))

    canvas._draw_deck_background()

    assert canvas._deck_drawn_bbox == (5, 6, 40, 20)
    assert canvas._deck_img_tk is None
    assert canvas.images == []


def test_redraw_keeps_key_overlay_when_backdrop_mode_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas._canvas_transform = lambda: object() if canvas._deck_drawn_bbox is not None else None

    monkeypatch.setattr(canvas_drawing, "calc_centered_drawn_bbox", lambda **_kwargs: (5, 6, 40, 20, 2.0))
    monkeypatch.setattr(canvas_drawing, "get_layout_keys", lambda *_args, **_kwargs: [_Key("k1", "Esc")])
    monkeypatch.setattr(canvas_drawing, "key_canvas_rect", lambda **_kwargs: (1.0, 2.0, 21.0, 12.0, 0.0))
    monkeypatch.setattr(canvas_drawing, "key_canvas_hit_rects", lambda **_kwargs: [(1.0, 2.0, 21.0, 12.0)])
    monkeypatch.setattr(
        canvas_drawing,
        "key_draw_style",
        lambda **_kwargs: _Style("#010203", "gray50", "#ffffff", 2, (), "#eeeeee"),
    )
    monkeypatch.setattr(canvas_drawing.tkfont, "Font", _FakeFont)

    canvas.redraw()

    assert canvas.images == []
    assert canvas._deck_drawn_bbox == (5, 6, 40, 20)
    assert len(canvas.rectangles) == 1
    assert canvas.rectangles[0]["tags"] == ("pslot_k1", "pkey_k1", "pkey")
    assert len(canvas.texts) == 1
    assert canvas.texts[0]["text"] == "Esc"


def test_draw_deck_background_uses_cache_and_transparency_var(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas._deck_img = Image.new("RGBA", (20, 10), color=(10, 20, 30, 255))
    canvas.editor.backdrop_transparency = _FakeVar("25")
    monkeypatch.setattr(canvas_drawing, "calc_centered_drawn_bbox", lambda **_kwargs: (5, 6, 40, 20, 2.0))

    canvas._draw_deck_background()

    assert canvas._deck_render_cache.get_calls == [
        {
            "deck_image": canvas._deck_img,
            "draw_size": (40, 20),
            "transparency_pct": 25.0,
            "photo_factory": canvas_drawing.ImageTk.PhotoImage,
        }
    ]
    assert canvas.images == [{"coords": (5, 6), "image": "photo", "anchor": "nw"}]
    assert canvas._deck_drawn_bbox == (5, 6, 40, 20)


def test_draw_deck_background_defaults_transparency_when_var_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas._deck_img = Image.new("RGBA", (20, 10), color=(10, 20, 30, 255))
    canvas.editor.backdrop_transparency = _FakeVar("25", exc=RuntimeError("boom"))
    monkeypatch.setattr(canvas_drawing, "calc_centered_drawn_bbox", lambda **_kwargs: (5, 6, 40, 20, 2.0))

    canvas._draw_deck_background()

    assert canvas._deck_render_cache.get_calls == [
        {
            "deck_image": canvas._deck_img,
            "draw_size": (40, 20),
            "transparency_pct": 0.0,
            "photo_factory": canvas_drawing.ImageTk.PhotoImage,
        }
    ]


def test_draw_deck_background_clears_cache_on_render_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    canvas = _FakeCanvas()
    canvas._deck_img = Image.new("RGBA", (20, 10), color=(10, 20, 30, 255))
    canvas._deck_render_cache.error = RuntimeError("bad image")
    canvas.editor.backdrop_transparency = _FakeVar(10)
    monkeypatch.setattr(canvas_drawing, "calc_centered_drawn_bbox", lambda **_kwargs: (1, 2, 30, 15, 1.5))

    with caplog.at_level(logging.ERROR, logger=canvas_drawing.__name__):
        canvas._draw_deck_background()

    assert canvas._deck_render_cache.clear_calls == 1
    assert canvas.images == []
    assert canvas._deck_img_tk is None
    assert canvas._deck_drawn_bbox == (1, 2, 30, 15)
    assert "Deck backdrop render failed; clearing cache and skipping the background image." in caplog.text


def test_update_key_visual_updates_fill_stipple_and_text_contrast() -> None:
    canvas = _FakeCanvas()
    canvas.key_rects = {"bright": 1, "dark": 2}
    canvas.key_texts = {"bright": 11, "dark": 22}

    canvas.update_key_visual("bright", (240, 240, 240))
    canvas.update_key_visual("dark", (10, 20, 30))

    assert canvas.itemconfig_calls == [
        (1, {"fill": "#f0f0f0", "stipple": "gray50"}),
        (11, {"fill": "#000000"}),
        (2, {"fill": "#0a141e", "stipple": "gray50"}),
        (22, {"fill": "#ffffff"}),
    ]


def test_update_key_visual_ignores_falsey_key_ids() -> None:
    canvas = _FakeCanvas()

    canvas.update_key_visual("", (1, 2, 3))

    assert canvas.itemconfig_calls == []
