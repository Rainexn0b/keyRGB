from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from .render import pace


def create_press_source(
    engine: Any,
    *,
    press_source_cls,
    open_keyboards,
    synthetic_fallback_enabled,
):
    devices = open_keyboards() or []
    return press_source_cls(
        devices=devices,
        synthetic=not bool(devices),
        spawn_interval_s=max(0.10, 0.45 / max(0.1, pace(engine))),
        allow_synthetic=synthetic_fallback_enabled(),
    )


def load_slot_keymap(*, loader) -> Mapping[str, Sequence[tuple[int, int]]]:
    return loader()


def mapped_slot_cells(
    slot_keymap: Mapping[str, Sequence[tuple[int, int]]],
    pressed_slot_id: object,
) -> Sequence[tuple[int, int]]:
    if not pressed_slot_id:
        return ()
    return slot_keymap.get(str(pressed_slot_id).lower(), ())
