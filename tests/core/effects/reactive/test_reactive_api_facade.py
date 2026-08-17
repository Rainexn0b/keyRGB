from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.core.effects.reactive import _effects_api
from src.core.effects.reactive.effects import _fade_api, _ripple_api

_FADE_MEMBERS = (
    "_PressSource",
    "_Pulse",
    "frame_dt_s",
    "create_press_source",
    "build_fade_overlay_into",
    "_set_reactive_active_pulse_mix",
    "_render_uniform_fallback",
    "render",
)
_RIPPLE_MEMBERS = (
    "_PressSource",
    "_RainbowPulse",
    "frame_dt_s",
    "create_press_source",
    "build_ripple_overlay_into",
    "build_ripple_color_map_into",
    "_set_reactive_active_pulse_mix",
    "_render_uniform_fallback",
    "render",
)


def test_reactive_facades_explicitly_satisfy_loop_dependencies() -> None:
    for member in _FADE_MEMBERS:
        assert callable(getattr(_fade_api, member))
    for member in _RIPPLE_MEMBERS:
        assert callable(getattr(_ripple_api, member))


def test_reactive_facade_is_immutable() -> None:
    with pytest.raises((FrozenInstanceError, AttributeError)):
        _fade_api.render = None


def test_reactive_api_no_longer_exposes_dynamic_module_binding_helpers() -> None:
    assert not hasattr(_effects_api, "bind_reactive_effect_exports")
    assert not hasattr(_effects_api, "reactive_fade_api_for")
    assert not hasattr(_effects_api, "reactive_ripple_api_for")
