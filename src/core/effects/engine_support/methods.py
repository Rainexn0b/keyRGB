from __future__ import annotations

from typing import Any, cast

from ..fades import fade_in_per_key, fade_uniform_color
from ..reactive.effects import run_reactive_fade, run_reactive_ripple
from ..software.effects import (
    run_chase,
    run_color_cycle,
    run_rainbow_swirl,
    run_rainbow_wave,
    run_spectrum_cycle,
    run_strobe,
    run_twinkle,
)
from ..timing import clamped_interval, get_interval


def get_interval_method(self, base_ms: int) -> float:
    return get_interval(base_ms, speed=int(self.speed))


def clamped_interval_method(self, base_ms: int, *, min_s: float) -> float:
    return clamped_interval(base_ms, speed=int(self.speed), min_s=float(min_s))


def fade_uniform_color_method(
    self,
    *,
    from_color: tuple,
    to_color: tuple,
    brightness: int,
    duration_s: float,
    steps: int = 18,
) -> None:
    fade_uniform_color(
        kb=self.kb,
        kb_lock=self.kb_lock,
        from_color=from_color,
        to_color=to_color,
        brightness=brightness,
        duration_s=duration_s,
        steps=steps,
    )


def fade_in_per_key_method(self, *, duration_s: float, steps: int = 12) -> None:
    fade_in_per_key(
        kb=self.kb,
        kb_lock=self.kb_lock,
        per_key_colors=self.per_key_colors,
        current_color=self.current_color,
        brightness=int(self.brightness),
        duration_s=duration_s,
        steps=steps,
    )


def effect_rainbow_wave_method(self) -> None:
    run_rainbow_wave(cast(Any, self))


def effect_rainbow_swirl_method(self) -> None:
    run_rainbow_swirl(cast(Any, self))


def effect_spectrum_cycle_method(self) -> None:
    run_spectrum_cycle(cast(Any, self))


def effect_color_cycle_method(self) -> None:
    run_color_cycle(cast(Any, self))


def effect_chase_method(self) -> None:
    run_chase(cast(Any, self))


def effect_twinkle_method(self) -> None:
    run_twinkle(cast(Any, self))


def effect_strobe_method(self) -> None:
    run_strobe(cast(Any, self))


def effect_reactive_fade_method(self) -> None:
    run_reactive_fade(cast(Any, self))


def effect_reactive_ripple_method(self) -> None:
    run_reactive_ripple(cast(Any, self))
