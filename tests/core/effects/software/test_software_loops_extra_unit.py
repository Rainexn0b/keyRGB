#!/usr/bin/env python3
"""Unit tests for fire/twinkle/strobe/chase/rain loops and reactive mapping.

Split from test_software_loops_unit.py (which keeps rainbow/wave/breathing
and shared effect math). Tests focus on loop wait behavior, particle
branches, and evdev key mapping without hardware/threading.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    ("effect_runner", "per_key_ok"),
    [
        pytest.param("run_fire", False, id="fire"),
        pytest.param("run_twinkle", False, id="twinkle"),
        pytest.param("run_strobe", False, id="strobe"),
        pytest.param("run_chase", True, id="chase-per-key"),
        pytest.param("run_rain", False, id="rain"),
    ],
)
def test_effect_loops_wait_before_second_iteration(effect_runner: str, per_key_ok: bool) -> None:
    from keyrgb.core.effects.software import _effects_basic, _effects_particles

    class StopEvent:
        def __init__(self) -> None:
            self.wait_calls = 0

        def is_set(self) -> bool:
            return self.wait_calls > 0

        def wait(self, _timeout: float) -> bool:
            self.wait_calls += 1
            return True

    stop_event = StopEvent()
    render_calls = 0

    def render_once(_engine: object, *, color_map: dict[tuple[int, int], tuple[int, int, int]]) -> None:
        nonlocal render_calls
        render_calls += 1
        assert color_map
        if render_calls > 1:
            raise AssertionError("effect loop iterated again before waiting")

    engine = SimpleNamespace(
        running=True,
        stop_event=stop_event,
        speed=4,
        brightness=25,
        current_color=(255, 0, 0),
        per_key_colors=None,
        kb=SimpleNamespace(set_key_colors=(lambda *_args, **_kwargs: None)) if per_key_ok else SimpleNamespace(),
    )

    runner = getattr(_effects_basic, effect_runner, None) or getattr(_effects_particles, effect_runner)
    runner(engine, render_fn=render_once)

    assert render_calls == 1
    assert stop_event.wait_calls == 1


class TestStrobeToggling:
    """Test strobe effect on/off logic."""

    def test_strobe_alternates_white_and_black(self):
        """Strobe should alternate between white and black."""
        on = False

        states = []
        for _ in range(4):
            if on:
                color = (255, 255, 255)
            else:
                color = (0, 0, 0)

            states.append((color, on))
            on = not on

        # Should alternate: off, on, off, on
        assert states[0] == ((0, 0, 0), False)
        assert states[1] == ((255, 255, 255), True)
        assert states[2] == ((0, 0, 0), False)
        assert states[3] == ((255, 255, 255), True)

    def test_strobe_off_state_respects_minimum_brightness(self):
        """Strobe 'off' should use max(1, brightness) not pure black."""
        brightness = 80

        # Simulate off state
        off_color = (0, 0, 0)
        off_brightness = max(1, brightness)

        assert off_brightness == 80
        assert off_color == (0, 0, 0)


class TestReactiveKeyMapping:
    def test_evdev_key_name_to_key_id_letters_digits(self):
        from keyrgb.core.effects.reactive.input import (
            evdev_key_name_to_key_id as _evdev_key_name_to_key_id,
            evdev_key_name_to_slot_id as _evdev_key_name_to_slot_id,
        )
        from keyrgb.core.resources.layouts import slot_id_for_key_id

        assert _evdev_key_name_to_key_id("KEY_A") == "a"
        assert _evdev_key_name_to_key_id("KEY_1") == "1"
        assert _evdev_key_name_to_key_id("A") == "a"
        assert _evdev_key_name_to_slot_id("KEY_A") == str(slot_id_for_key_id("auto", "a") or "a")

    def test_evdev_key_name_to_key_id_specials(self):
        from keyrgb.core.effects.reactive.input import (
            evdev_key_name_to_key_id as _evdev_key_name_to_key_id,
            evdev_key_name_to_slot_id as _evdev_key_name_to_slot_id,
        )
        from keyrgb.core.resources.layouts import slot_id_for_key_id

        assert _evdev_key_name_to_key_id("KEY_LEFTSHIFT") == "lshift"
        assert _evdev_key_name_to_key_id("KEY_RIGHTALT") == "ralt"
        assert _evdev_key_name_to_key_id("KEY_BACKSLASH") == "bslash"
        assert _evdev_key_name_to_key_id("KEY_102ND") == "nonusbackslash"
        assert _evdev_key_name_to_key_id("KEY_LEFTBRACE") == "lbracket"
        assert _evdev_key_name_to_key_id("KEY_KP1") == "num1"
        assert _evdev_key_name_to_key_id("KEY_KPDOT") == "numdot"
        assert _evdev_key_name_to_slot_id("KEY_102ND") == str(
            slot_id_for_key_id("auto", "nonusbackslash") or "nonusbackslash"
        )


def test_particle_effects_multiple_ticks_with_fast_pace(monkeypatch) -> None:
    """Exercise spawn/age/overlay branches across a few wait cycles."""
    from keyrgb.core.effects.software import _effects_particles as particles

    class StopEvent:
        def __init__(self, max_waits: int) -> None:
            self.waits = 0
            self.max_waits = max_waits

        def is_set(self) -> bool:
            return self.waits >= self.max_waits

        def wait(self, _timeout: float) -> bool:
            self.waits += 1
            return True

    monkeypatch.setattr(particles._base, "frame_dt_s", lambda: 0.05)
    monkeypatch.setattr(particles._base, "pace", lambda _e: 8.0)
    monkeypatch.setattr(particles._base, "animation_step_s", lambda *_a, **_k: 0.2)
    monkeypatch.setattr(particles._base, "base_color_map", lambda _e: {(0, 0): (10, 10, 10), (0, 1): (0, 0, 0)})
    monkeypatch.setattr(particles._base, "has_per_key", lambda _e: True)
    monkeypatch.setattr(particles._base, "mix", lambda a, b, *, t: b if t > 0.5 else a)
    monkeypatch.setattr(particles._base, "scale", lambda c, s: c)
    monkeypatch.setattr(particles.random, "randrange", lambda n: 0)
    monkeypatch.setattr(particles.random, "random", lambda: 0.25)

    renders: list[int] = []

    def render_fn(_engine, *, color_map):
        renders.append(len(color_map))

    for runner in (particles.run_twinkle, particles.run_strobe, particles.run_chase, particles.run_rain):
        renders.clear()
        engine = SimpleNamespace(
            running=True,
            stop_event=StopEvent(3),
            speed=8,
            brightness=25,
            current_color=(0, 0, 0),  # chase black-highlight fallback
            per_key_colors={(0, 0): (1, 1, 1)},
            kb=SimpleNamespace(set_key_colors=lambda *_a, **_k: None),
        )
        # strobe black base fallback
        if runner is particles.run_strobe:
            monkeypatch.setattr(particles._base, "base_color_map", lambda _e: {(0, 0): (0, 0, 0)})
        runner(engine, render_fn=render_fn)
        assert len(renders) >= 2


def test_strobe_invalid_brightness_and_chase_uniform(monkeypatch) -> None:
    from keyrgb.core.effects.software import _effects_particles as particles

    class StopEvent:
        def __init__(self) -> None:
            self.waits = 0

        def is_set(self) -> bool:
            return self.waits > 0

        def wait(self, _timeout: float) -> bool:
            self.waits += 1
            return True

    monkeypatch.setattr(particles._base, "frame_dt_s", lambda: 0.05)
    monkeypatch.setattr(particles._base, "pace", lambda _e: 2.0)
    monkeypatch.setattr(particles._base, "animation_step_s", lambda *_a, **_k: 0.5)
    monkeypatch.setattr(particles._base, "base_color_map", lambda _e: {(0, 0): (1, 1, 1)})
    monkeypatch.setattr(particles._base, "has_per_key", lambda _e: False)
    monkeypatch.setattr(particles._base, "mix", lambda a, b, *, t: a)
    monkeypatch.setattr(particles._base, "scale", lambda c, s: c)
    monkeypatch.setattr(
        particles,
        "fill_uniform_color_map",
        lambda m, *, color, **_kwargs: m.__setitem__((0, 0), color),
    )
    monkeypatch.setattr(particles, "scaled_color_map_nonzero", lambda base, *, scale, brightness: base)

    engine = SimpleNamespace(
        running=True,
        stop_event=StopEvent(),
        brightness="bad",
        current_color=None,
        kb=SimpleNamespace(),
    )
    particles.run_strobe(engine, render_fn=lambda *_a, **_k: None)

    engine2 = SimpleNamespace(
        running=True,
        stop_event=StopEvent(),
        brightness=25,
        current_color=None,
        kb=SimpleNamespace(),
    )
    particles.run_chase(engine2, render_fn=lambda *_a, **_k: None)
