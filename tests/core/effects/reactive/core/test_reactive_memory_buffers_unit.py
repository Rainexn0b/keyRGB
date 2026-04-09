from __future__ import annotations

import pytest

from src.core.effects.reactive._ripple_helpers import (
    build_fade_overlay_into,
    build_ripple_color_map_into,
    build_ripple_overlay_into,
    get_engine_overlay_buffer,
)
from src.core.effects.reactive.utils import _Pulse, _RainbowPulse, _age_pulses_in_place


def test_age_pulses_in_place_reuses_list_and_drops_expired() -> None:
    pulses = [
        _Pulse(row=0, col=0, age_s=0.1, ttl_s=0.5),
        _Pulse(row=1, col=1, age_s=0.4, ttl_s=0.5),
    ]

    result = _age_pulses_in_place(pulses, dt=0.15)

    assert result is pulses
    assert len(pulses) == 1
    assert pulses[0].row == 0
    assert pulses[0].col == 0


def test_build_fade_overlay_into_reuses_dest() -> None:
    dest = {(9, 9): 0.5}
    pulses = [
        _Pulse(row=0, col=0, age_s=0.1, ttl_s=0.5),
        _Pulse(row=0, col=0, age_s=0.2, ttl_s=0.5),
        _Pulse(row=1, col=1, age_s=0.3, ttl_s=0.5),
    ]

    result = build_fade_overlay_into(dest, pulses)

    assert result is dest
    assert (9, 9) not in dest
    assert dest[(0, 0)] > dest[(1, 1)]


def test_get_engine_overlay_buffer_bypasses_hostile_engine_attribute_lookup() -> None:
    class _HostileEngine:
        def __getattribute__(self, name: str):
            if name == "_reactive_fade_overlay":
                raise RuntimeError("hostile attribute lookup")
            return object.__getattribute__(self, name)

    engine = _HostileEngine()

    first = get_engine_overlay_buffer(engine, "_reactive_fade_overlay")
    second = get_engine_overlay_buffer(engine, "_reactive_fade_overlay")

    assert first == {}
    assert second is first
    assert vars(engine)["_reactive_fade_overlay"] is first


def test_get_engine_overlay_buffer_degrades_when_engine_cannot_store_buffers() -> None:
    class _SlotOnlyEngine:
        __slots__ = ()

    engine = _SlotOnlyEngine()

    first = get_engine_overlay_buffer(engine, "_reactive_fade_overlay")
    second = get_engine_overlay_buffer(engine, "_reactive_fade_overlay")

    assert first == {}
    assert second == {}
    assert second is not first


def test_get_engine_overlay_buffer_reraises_unexpected_assignment_failures() -> None:
    class _BrokenSlotEngine:
        __slots__ = ()

        def __setattr__(self, name: str, value: object) -> None:
            raise RuntimeError(f"unexpected failure assigning {name}={value}")

    with pytest.raises(RuntimeError, match="unexpected failure assigning _reactive_fade_overlay"):
        get_engine_overlay_buffer(_BrokenSlotEngine(), "_reactive_fade_overlay")


def test_build_ripple_overlay_into_reuses_dest() -> None:
    dest = {(8, 8): (0.1, 90.0)}
    pulses = [_RainbowPulse(row=1, col=1, age_s=0.1, ttl_s=0.8, hue_offset=45.0)]

    result = build_ripple_overlay_into(dest, pulses, band=2.15)

    assert result is dest
    assert (8, 8) not in dest
    assert dest


def test_build_ripple_color_map_into_reuses_dest() -> None:
    dest = {(9, 9): (1, 1, 1)}
    base = {(0, 0): (10, 20, 30), (0, 1): (40, 50, 60)}
    base_unscaled = dict(base)
    overlay = {(0, 0): (1.0, 180.0)}

    result = build_ripple_color_map_into(
        dest,
        base=base,
        base_unscaled=base_unscaled,
        overlay=overlay,
        per_key_backdrop_active=False,
        manual=None,
        pulse_scale=1.0,
    )

    assert result is dest
    assert (9, 9) not in dest
    assert dest[(0, 1)] == (40, 50, 60)


def test_build_ripple_color_map_into_per_key_backdrop_scales_mix_weight_not_rgb() -> None:
    """per_key_backdrop + no manual: pulse_scale controls mix weight, not RGB scaling.
    This keeps the brightness slider effective even when the contrasting highlight is
    black (e.g. against an all-white backdrop where scale(black, x) == black for any x)."""
    base_white = {(0, 0): (255, 255, 255)}
    base_unscaled_white = {(0, 0): (255, 255, 255)}
    overlay_full = {(0, 0): (1.0, 120.0)}  # full weight, hue=green

    result_low = build_ripple_color_map_into(
        {},
        base=base_white,
        base_unscaled=base_unscaled_white,
        overlay=overlay_full,
        per_key_backdrop_active=True,
        manual=None,
        pulse_scale=0.2,
    )
    result_high = build_ripple_color_map_into(
        {},
        base=base_white,
        base_unscaled=base_unscaled_white,
        overlay=overlay_full,
        per_key_backdrop_active=True,
        manual=None,
        pulse_scale=1.0,
    )

    # Different scales must produce different key colors
    assert result_low[(0, 0)] != result_high[(0, 0)]

    # At scale=0, the key stays at its backdrop color (mix weight = 0)
    result_zero = build_ripple_color_map_into(
        {},
        base=base_white,
        base_unscaled=base_unscaled_white,
        overlay=overlay_full,
        per_key_backdrop_active=True,
        manual=None,
        pulse_scale=0.0,
    )
    assert result_zero[(0, 0)] == (255, 255, 255)


def test_build_ripple_color_map_into_no_per_key_backdrop_still_scales_rgb() -> None:
    """Without per_key_backdrop, pulse_scale is applied to the RGB color directly (unchanged path)."""
    base_dark = {(0, 0): (5, 5, 5)}
    base_unscaled_dark = {(0, 0): (5, 5, 5)}
    overlay_full = {(0, 0): (1.0, 120.0)}

    result_dim = build_ripple_color_map_into(
        {},
        base=base_dark,
        base_unscaled=base_unscaled_dark,
        overlay=overlay_full,
        per_key_backdrop_active=False,
        manual=None,
        pulse_scale=0.1,
    )
    result_bright = build_ripple_color_map_into(
        {},
        base=base_dark,
        base_unscaled=base_unscaled_dark,
        overlay=overlay_full,
        per_key_backdrop_active=False,
        manual=None,
        pulse_scale=1.0,
    )

    assert result_dim[(0, 0)] != result_bright[(0, 0)]
    assert sum(result_dim[(0, 0)]) < sum(result_bright[(0, 0)])


def test_build_ripple_color_map_into_dark_profile_per_key_backdrop_scales_mix_weight() -> None:
    """Dark profile (all-black per-key backdrop) with no manual color: pulse_scale controls
    mix weight so the reactive brightness slider remains effective. The brightness-boost
    contrasting highlight chosen against black is white; scale(white, 0.1) != white, but
    mix weight path handles both dark and light backdrops without the RGB=black edge case."""
    base_black = {(0, 0): (0, 0, 0)}
    overlay_full = {(0, 0): (1.0, 200.0)}  # full weight, hue=purple

    result_dim = build_ripple_color_map_into(
        {},
        base=base_black,
        base_unscaled=base_black,
        overlay=overlay_full,
        per_key_backdrop_active=True,
        manual=None,
        pulse_scale=0.1,
    )
    result_bright = build_ripple_color_map_into(
        {},
        base=base_black,
        base_unscaled=base_black,
        overlay=overlay_full,
        per_key_backdrop_active=True,
        manual=None,
        pulse_scale=1.0,
    )

    # Brighter scale must produce a key color with higher total channel sum
    assert sum(result_dim[(0, 0)]) < sum(result_bright[(0, 0)])

    # At scale=0, the key stays at backdrop black
    result_zero = build_ripple_color_map_into(
        {},
        base=base_black,
        base_unscaled=base_black,
        overlay=overlay_full,
        per_key_backdrop_active=True,
        manual=None,
        pulse_scale=0.0,
    )
    assert result_zero[(0, 0)] == (0, 0, 0)


def test_build_ripple_overlay_into_band_controls_ring_width() -> None:
    """Wider band means more keys are illuminated around the wavefront."""
    from src.core.effects.reactive._ripple_helpers import build_ripple_overlay_into
    from src.core.effects.reactive.utils import _RainbowPulse

    pulse = _RainbowPulse(row=3, col=10, age_s=0.3, ttl_s=0.65, hue_offset=0.0)

    narrow = {}
    build_ripple_overlay_into(narrow, [pulse], band=1.0)

    wide = {}
    build_ripple_overlay_into(wide, [pulse], band=4.0)

    # Wider band lights up more keys
    assert len(wide) > len(narrow)
