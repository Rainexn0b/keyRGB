from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = tuple[int, int, int]
Key = tuple[int, int]

_ALL_KEYS: tuple[Key, ...] = tuple((r, c) for r in range(NUM_ROWS) for c in range(NUM_COLS))


def get_engine_color_map_buffer(engine: EffectsEngine, attr_name: str) -> dict[Key, Color]:
    try:
        engine_state = object.__getattribute__(engine, "__dict__")
    except (AttributeError, TypeError):
        engine_state = None

    if isinstance(engine_state, dict):
        existing = engine_state.get(attr_name)
        if isinstance(existing, dict):
            return existing

        created: dict[Key, Color] = {}
        engine_state[attr_name] = created
        return created

    created: dict[Key, Color] = {}  # type: ignore[no-redef]
    try:
        setattr(engine, attr_name, created)
    except (AttributeError, TypeError):
        pass
    return created


def fill_uniform_color_map(dest: dict[Key, Color], *, color: Color) -> dict[Key, Color]:
    dest.clear()
    for key in _ALL_KEYS:
        dest[key] = color
    return dest


def scale_color_map_into(dest: dict[Key, Color], *, source: dict[Key, Color], factor: float) -> dict[Key, Color]:
    dest.clear()
    f = float(factor)
    for key, rgb in source.items():
        dest[key] = (
            round(rgb[0] * f),
            round(rgb[1] * f),
            round(rgb[2] * f),
        )
    return dest
