"""Software-rendered effect implementations.

This module intentionally stays small: individual effect implementations live in
adjacent helper modules, but the public import path remains
`src.core.effects.software.effects`.
"""

from __future__ import annotations

from .base import render
from ._effects_basic import (
    run_breathing as _run_breathing,
    run_color_cycle as _run_color_cycle,
    run_fire as _run_fire,
    run_rainbow_swirl as _run_rainbow_swirl,
    run_rainbow_wave as _run_rainbow_wave,
    run_random as _run_random,
    run_spectrum_cycle as _run_spectrum_cycle,
)
from ._effects_particles import (
    run_chase as _run_chase,
    run_rain as _run_rain,
    run_strobe as _run_strobe,
    run_twinkle as _run_twinkle,
)


def run_breathing(engine) -> None:
    _run_breathing(engine, render_fn=render)


def run_fire(engine) -> None:
    _run_fire(engine, render_fn=render)


def run_random(engine) -> None:
    _run_random(engine, render_fn=render)


def run_rainbow_wave(engine) -> None:
    _run_rainbow_wave(engine, render_fn=render)


def run_rainbow_swirl(engine) -> None:
    _run_rainbow_swirl(engine, render_fn=render)


def run_spectrum_cycle(engine) -> None:
    _run_spectrum_cycle(engine, render_fn=render)


def run_color_cycle(engine) -> None:
    _run_color_cycle(engine, render_fn=render)


def run_twinkle(engine) -> None:
    _run_twinkle(engine, render_fn=render)


def run_strobe(engine) -> None:
    _run_strobe(engine, render_fn=render)


def run_chase(engine) -> None:
    _run_chase(engine, render_fn=render)


def run_rain(engine) -> None:
    _run_rain(engine, render_fn=render)


__all__ = [
    "run_breathing",
    "run_fire",
    "run_random",
    "run_rainbow_wave",
    "run_rainbow_swirl",
    "run_spectrum_cycle",
    "run_color_cycle",
    "run_twinkle",
    "run_strobe",
    "run_chase",
    "run_rain",
]
