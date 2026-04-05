from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Protocol

from .input import EvdevKeyboardDevices
from .render import pace

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Key = tuple[int, int]
SlotKeyMap = Mapping[str, Sequence[Key]]


class _PressSourceProtocol(Protocol):
    spawn_interval_s: float


class _PressSourceFactoryProtocol(Protocol):
    def __call__(
        self,
        *,
        devices: EvdevKeyboardDevices,
        synthetic: bool,
        spawn_interval_s: float,
        allow_synthetic: bool,
    ) -> _PressSourceProtocol: ...


def create_press_source(
    engine: "EffectsEngine",
    *,
    press_source_cls: _PressSourceFactoryProtocol,
    open_keyboards: Callable[[], EvdevKeyboardDevices | None],
    synthetic_fallback_enabled: Callable[[], bool],
) -> _PressSourceProtocol:
    devices = open_keyboards() or []
    return press_source_cls(
        devices=devices,
        synthetic=not bool(devices),
        spawn_interval_s=max(0.10, 0.45 / max(0.1, pace(engine))),
        allow_synthetic=bool(synthetic_fallback_enabled()),
    )


def load_slot_keymap(*, loader: Callable[[], SlotKeyMap]) -> SlotKeyMap:
    return loader()


def mapped_slot_cells(
    slot_keymap: SlotKeyMap,
    pressed_slot_id: object,
) -> Sequence[Key]:
    if not pressed_slot_id:
        return ()
    return slot_keymap.get(str(pressed_slot_id).lower(), ())
