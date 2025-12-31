from __future__ import annotations

from dataclasses import dataclass

from src.gui.perkey.ui.full_map import ensure_full_map_ui


@dataclass
class DummyConfig:
    color: tuple[int, int, int]


@dataclass
class DummyEditor:
    config: DummyConfig
    colors: dict
    _last_non_black_color: tuple[int, int, int] | None = None


def test_ensure_full_map_ui_prefers_last_non_black_color_as_base() -> None:
    ed = DummyEditor(
        config=DummyConfig(color=(10, 20, 30)),
        colors={(0, 0): (1, 2, 3)},
        _last_non_black_color=(7, 8, 9),
    )

    captured = {}

    def ensure_fn(*, colors, num_rows: int, num_cols: int, base_color, fallback_color):
        captured["colors"] = dict(colors)
        captured["num_rows"] = num_rows
        captured["num_cols"] = num_cols
        captured["base_color"] = tuple(base_color)
        captured["fallback_color"] = tuple(fallback_color)
        return {"ok": True}

    ensure_full_map_ui(ed, num_rows=3, num_cols=4, ensure_fn=ensure_fn)

    assert captured == {
        "colors": {(0, 0): (1, 2, 3)},
        "num_rows": 3,
        "num_cols": 4,
        "base_color": (7, 8, 9),
        "fallback_color": (10, 20, 30),
    }
    assert ed.colors == {"ok": True}


def test_ensure_full_map_ui_falls_back_to_config_color_when_no_last_non_black() -> None:
    ed = DummyEditor(
        config=DummyConfig(color=(10, 20, 30)),
        colors={},
        _last_non_black_color=None,
    )

    captured = {}

    def ensure_fn(*, colors, num_rows: int, num_cols: int, base_color, fallback_color):
        captured["base_color"] = tuple(base_color)
        captured["fallback_color"] = tuple(fallback_color)
        return {"ok": True}

    ensure_full_map_ui(ed, num_rows=1, num_cols=1, ensure_fn=ensure_fn)

    assert captured["base_color"] == (10, 20, 30)
    assert captured["fallback_color"] == (10, 20, 30)
    assert ed.colors == {"ok": True}
