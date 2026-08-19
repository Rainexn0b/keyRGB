from __future__ import annotations

from .render import Color


def get_engine_manual_reactive_color(engine: object) -> Color | None:
    if not bool(getattr(engine, "reactive_use_manual_color", False)):
        return None
    src = getattr(engine, "reactive_color", None)
    if src is None:
        return None
    try:
        return (int(src[0]), int(src[1]), int(src[2]))
    except (TypeError, ValueError, IndexError):
        return None


def get_engine_reactive_color(engine: object) -> Color:
    manual = get_engine_manual_reactive_color(engine)
    if manual is not None:
        return manual
    src = getattr(engine, "current_color", None) or (255, 255, 255)
    return (int(src[0]), int(src[1]), int(src[2]))
