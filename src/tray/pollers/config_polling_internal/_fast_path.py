from __future__ import annotations

from typing import Literal, Protocol


FastPathChangeKind = Literal["none", "target_only", "reactive_only", "brightness_only"]
ColorTuple = tuple[int, int, int]


class _FastPathComparableState(Protocol):
    @property
    def effect(self) -> str: ...

    @property
    def speed(self) -> int: ...

    @property
    def brightness(self) -> int: ...

    @property
    def color(self) -> ColorTuple: ...

    @property
    def perkey_sig(self) -> tuple | None: ...

    @property
    def reactive_use_manual(self) -> bool: ...

    @property
    def reactive_color(self) -> ColorTuple: ...

    @property
    def reactive_brightness(self) -> int: ...

    @property
    def reactive_trail_percent(self) -> int: ...

    @property
    def software_effect_target(self) -> str: ...


_FAST_PATH_CLASSIFICATION_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)


def classify_fast_path_change(
    *,
    last_applied: _FastPathComparableState | None,
    current: _FastPathComparableState,
) -> FastPathChangeKind:
    if last_applied is None:
        return "none"

    try:
        if _is_target_only_change(last_applied, current):
            return "target_only"
    except _FAST_PATH_CLASSIFICATION_EXCEPTIONS:
        pass

    try:
        if _is_reactive_only_change(last_applied, current):
            return "reactive_only"
    except _FAST_PATH_CLASSIFICATION_EXCEPTIONS:
        pass

    try:
        if _is_brightness_only_change(last_applied, current):
            return "brightness_only"
    except _FAST_PATH_CLASSIFICATION_EXCEPTIONS:
        pass

    return "none"


def _is_target_only_change(
    last_applied: _FastPathComparableState,
    current: _FastPathComparableState,
) -> bool:
    return (
        last_applied.effect == current.effect
        and last_applied.speed == current.speed
        and last_applied.brightness == current.brightness
        and last_applied.color == current.color
        and last_applied.perkey_sig == current.perkey_sig
        and last_applied.reactive_use_manual == current.reactive_use_manual
        and last_applied.reactive_color == current.reactive_color
        and last_applied.reactive_brightness == current.reactive_brightness
        and last_applied.software_effect_target != current.software_effect_target
    )


def _is_reactive_only_change(
    last_applied: _FastPathComparableState,
    current: _FastPathComparableState,
) -> bool:
    return (
        last_applied.effect == current.effect
        and last_applied.speed == current.speed
        and last_applied.brightness == current.brightness
        and last_applied.color == current.color
        and last_applied.perkey_sig == current.perkey_sig
        and last_applied.software_effect_target == current.software_effect_target
        and (
            last_applied.reactive_use_manual != current.reactive_use_manual
            or last_applied.reactive_color != current.reactive_color
            or last_applied.reactive_brightness != current.reactive_brightness
            or last_applied.reactive_trail_percent != current.reactive_trail_percent
        )
    )


def _is_brightness_only_change(
    last_applied: _FastPathComparableState,
    current: _FastPathComparableState,
) -> bool:
    return (
        last_applied.effect == current.effect
        and last_applied.speed == current.speed
        and last_applied.color == current.color
        and last_applied.perkey_sig == current.perkey_sig
        and last_applied.software_effect_target == current.software_effect_target
        and last_applied.reactive_use_manual == current.reactive_use_manual
        and last_applied.reactive_color == current.reactive_color
        and last_applied.reactive_brightness == current.reactive_brightness
        and last_applied.brightness != current.brightness
    )
