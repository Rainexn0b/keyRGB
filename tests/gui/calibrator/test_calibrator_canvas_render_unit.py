from __future__ import annotations

from types import SimpleNamespace

import pytest
from PIL import Image

import src.gui.calibrator.helpers.canvas_render as canvas_render


class _FakeCanvas:
    def __init__(self) -> None:
        self.delete_calls: list[str] = []
        self.image_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.rectangle_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.text_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.width = 400
        self.height = 200

    def delete(self, tag: str) -> None:
        self.delete_calls.append(tag)

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height

    def create_image(self, *args: object, **kwargs: object) -> None:
        self.image_calls.append((args, dict(kwargs)))

    def create_rectangle(self, *args: object, **kwargs: object) -> None:
        self.rectangle_calls.append((args, dict(kwargs)))

    def create_text(self, *args: object, **kwargs: object) -> None:
        self.text_calls.append((args, dict(kwargs)))


class _FakeCache:
    def __init__(self, result: object = "deck-photo") -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def get_or_create(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        return self.result


class _FakeFont:
    def __init__(self, font: tuple[str, int]) -> None:
        self.size = int(font[1])

    def configure(self, *, size: int) -> None:
        self.size = int(size)

    def measure(self, text: str) -> int:
        if text == "…":
            return 2
        return len(text) * 4


def _key(key_id: str, label: str) -> SimpleNamespace:
    return SimpleNamespace(key_id=key_id, label=label)


def test_redraw_calibration_canvas_draws_backdrop_keys_and_text(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    deck_pil = Image.new("RGBA", (20, 10), color=(1, 2, 3, 255))
    cache = _FakeCache()
    transform = object()
    monkeypatch.setattr(canvas_render, "calc_centered_drawn_bbox", lambda **_kwargs: (5, 6, 40, 20, 2.0))
    monkeypatch.setattr(canvas_render, "transform_from_drawn_bbox", lambda **_kwargs: transform)
    monkeypatch.setattr(canvas_render, "get_layout_keys", lambda *_args, **_kwargs: [_key("esc", "Escape")])
    monkeypatch.setattr(canvas_render, "key_canvas_bbox", lambda **_kwargs: (1.0, 2.0, 21.0, 12.0))
    monkeypatch.setattr(
        canvas_render,
        "key_draw_style",
        lambda **_kwargs: SimpleNamespace(
            outline="#fff", width=2, fill="#123", stipple="gray50", dash=(2, 1), text_fill="#eee"
        ),
    )
    monkeypatch.setattr(canvas_render, "_fit_key_label", lambda label, *, key_w, key_h: (label[:3], 9))

    out_transform, deck_tk = canvas_render.redraw_calibration_canvas(
        canvas=canvas,
        deck_pil=deck_pil,
        deck_render_cache=cache,
        layout_tweaks={},
        per_key_layout_tweaks={},
        keymap={"esc": (0, 0)},
        selected_key_id="esc",
        physical_layout="iso",
        legend_pack_id="iso-de-qwertz",
        slot_overrides={"foo": {"visible": True}},
    )

    assert out_transform is transform
    assert deck_tk == "deck-photo"
    assert canvas.delete_calls == ["all"]
    assert cache.calls == [
        {
            "deck_image": deck_pil,
            "draw_size": (40, 20),
            "transparency_pct": 0.0,
            "photo_factory": canvas_render.ImageTk.PhotoImage,
        }
    ]
    assert canvas.image_calls == [((5, 6), {"anchor": "nw", "image": "deck-photo"})]
    assert canvas.rectangle_calls[0][1]["tags"] == ("pkey_esc", "pkey")
    assert canvas.text_calls[0][1]["text"] == "Esc"


def test_redraw_calibration_canvas_passes_legend_pack_to_layout_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    transform = object()
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(canvas_render, "calc_centered_drawn_bbox", lambda **_kwargs: (0, 0, 20, 10, 1.0))
    monkeypatch.setattr(canvas_render, "transform_from_drawn_bbox", lambda **_kwargs: transform)
    monkeypatch.setattr(
        canvas_render,
        "get_layout_keys",
        lambda *args, **kwargs: calls.append({"args": args, "kwargs": dict(kwargs)}) or [],
    )

    canvas_render.redraw_calibration_canvas(
        canvas=canvas,
        deck_pil=None,
        deck_render_cache=_FakeCache(),
        layout_tweaks={},
        per_key_layout_tweaks={},
        keymap={},
        physical_layout="iso",
        legend_pack_id="iso-de-qwertz",
    )

    assert calls == [{"args": ("iso",), "kwargs": {"legend_pack_id": "iso-de-qwertz", "slot_overrides": None}}]


def test_redraw_calibration_canvas_skips_backdrop_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    cache = _FakeCache()
    transform = object()
    monkeypatch.setattr(canvas_render, "calc_centered_drawn_bbox", lambda **_kwargs: (0, 0, 20, 10, 1.0))
    monkeypatch.setattr(canvas_render, "transform_from_drawn_bbox", lambda **_kwargs: transform)
    monkeypatch.setattr(canvas_render, "get_layout_keys", lambda *_args, **_kwargs: [])

    out_transform, deck_tk = canvas_render.redraw_calibration_canvas(
        canvas=canvas,
        deck_pil=None,
        deck_render_cache=cache,
        layout_tweaks={},
        per_key_layout_tweaks={},
        keymap={},
        selected_key_id=None,
    )

    assert out_transform is transform
    assert deck_tk is None
    assert cache.calls == []
    assert canvas.image_calls == []


def test_fit_key_label_shrinks_and_ellipsizes_when_needed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canvas_render.tkfont, "Font", _FakeFont)

    label, size = canvas_render._fit_key_label("LongLegend", key_w=12, key_h=12)

    assert label.endswith("…")
    assert size >= 6


def test_fit_key_label_falls_back_cleanly_on_font_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_font(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(canvas_render.tkfont, "Font", raise_font)

    label, size = canvas_render._fit_key_label("Label", key_w=20, key_h=10)

    assert label == "Label"
    assert size == 7
