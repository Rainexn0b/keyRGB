from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Tuple

from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = Tuple[int, int, int]
Key = Tuple[int, int]

_ALL_KEYS: tuple[Key, ...] = tuple((r, c) for r in range(NUM_ROWS) for c in range(NUM_COLS))


def get_engine_color_map_buffer(engine: "EffectsEngine", attr_name: str) -> Dict[Key, Color]:
    try:
        engine_state = object.__getattribute__(engine, "__dict__")
    except (AttributeError, TypeError):
        engine_state = None

    if isinstance(engine_state, dict):
        existing = engine_state.get(attr_name)
        if isinstance(existing, dict):
            return existing

        created: Dict[Key, Color] = {}
        engine_state[attr_name] = created
        return created

    created: Dict[Key, Color] = {}  # type: ignore[no-redef]
    try:
        setattr(engine, attr_name, created)
    except (AttributeError, TypeError):
        pass
    return created


def fill_uniform_color_map(dest: Dict[Key, Color], *, color: Color) -> Dict[Key, Color]:
    dest.clear()
    for key in _ALL_KEYS:
        dest[key] = color
    return dest


def scale_color_map_into(dest: Dict[Key, Color], *, source: Dict[Key, Color], factor: float) -> Dict[Key, Color]:
    dest.clear()
    f = float(factor)
    for key, rgb in source.items():
        dest[key] = (
            int(round(rgb[0] * f)),
            int(round(rgb[1] * f)),
            int(round(rgb[2] * f)),
        )
    return dest
