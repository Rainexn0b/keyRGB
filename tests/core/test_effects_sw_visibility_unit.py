from __future__ import annotations

import os
import random
import threading
import time

from src.core.effects.engine import EffectsEngine
import src.core.effects.reactive.effects as reactive_effects
from src.core.effects.reactive.effects import run_reactive_fade
from src.core.effects.software.effects import run_chase
from src.core.resources.layouts import slot_id_for_key_id


class UniformOnlyKeyboard:
    def __init__(self):
        self.calls: list[tuple[int, int, int]] = []

    def set_color(self, color, *, brightness: int):
        r, g, b = color
        self.calls.append((int(r), int(g), int(b)))


def _run_for(engine: EffectsEngine, target, seconds: float) -> None:
    engine.running = True
    engine.stop_event.clear()
    t = threading.Thread(target=target, args=(engine,), daemon=True)
    t.start()
    time.sleep(seconds)
    engine.running = False
    engine.stop_event.set()
    t.join(timeout=1.0)


def test_chase_is_visibly_animated_without_perkey() -> None:
    random.seed(0)

    engine = EffectsEngine()
    engine.kb = UniformOnlyKeyboard()
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.speed = 8
    engine.brightness = 25
    engine.current_color = (0, 200, 255)
    engine.per_key_colors = None

    _run_for(engine, run_chase, 0.20)

    calls = engine.kb.calls
    assert len(calls) >= 3
    assert len(set(calls)) >= 2


def test_reactive_fade_has_fallback_animation_without_evdev() -> None:
    random.seed(0)

    old_disable_evdev = os.environ.get("KEYRGB_DISABLE_EVDEV")
    old_synthetic = os.environ.get("KEYRGB_REACTIVE_SYNTHETIC_FALLBACK")
    os.environ["KEYRGB_DISABLE_EVDEV"] = "1"
    os.environ["KEYRGB_REACTIVE_SYNTHETIC_FALLBACK"] = "1"

    engine = EffectsEngine()
    engine.kb = UniformOnlyKeyboard()
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.speed = 8
    engine.brightness = 25
    engine.current_color = (255, 0, 0)
    engine.per_key_colors = None

    try:
        _run_for(engine, run_reactive_fade, 0.35)
    finally:
        if old_disable_evdev is None:
            os.environ.pop("KEYRGB_DISABLE_EVDEV", None)
        else:
            os.environ["KEYRGB_DISABLE_EVDEV"] = old_disable_evdev
        if old_synthetic is None:
            os.environ.pop("KEYRGB_REACTIVE_SYNTHETIC_FALLBACK", None)
        else:
            os.environ["KEYRGB_REACTIVE_SYNTHETIC_FALLBACK"] = old_synthetic

    calls = engine.kb.calls
    assert len(calls) >= 3
    assert len(set(calls)) >= 2


def test_reactive_fade_fans_out_one_keypress_to_all_mapped_cells(monkeypatch) -> None:
    captured_pulses: list[tuple[int, int]] = []

    class _StopEvent:
        def __init__(self) -> None:
            self._set = False

        def is_set(self) -> bool:
            return self._set

        def wait(self, _timeout: float) -> bool:
            self._set = True
            return False

    class _PressSource:
        def __init__(self, *args, **kwargs) -> None:
            self._used = False
            self.devices = []
            self.synthetic = False
            self.spawn_interval_s = 0.1

        def poll_slot_id(self, *, dt: float):
            if self._used:
                return None
            self._used = True
            return str(slot_id_for_key_id("auto", "enter") or "enter")

        def close(self) -> None:
            return None

    class _PerKeyKeyboard:
        def set_key_colors(self, _colors):
            return None

    engine = EffectsEngine()
    engine.running = True
    engine.stop_event = _StopEvent()
    engine.kb = _PerKeyKeyboard()
    engine.brightness = 25
    engine.reactive_brightness = 25
    engine.current_color = (255, 0, 0)
    engine.per_key_colors = None

    monkeypatch.setattr(reactive_effects, "frame_dt_s", lambda: 0.01)
    monkeypatch.setattr(reactive_effects, "try_open_evdev_keyboards", lambda: [])
    monkeypatch.setattr(reactive_effects, "_PressSource", _PressSource)
    monkeypatch.setattr(reactive_effects, "pace", lambda _engine: 1.0)
    monkeypatch.setattr(
        reactive_effects,
        "load_active_profile_slot_keymap",
        lambda: {str(slot_id_for_key_id("auto", "enter") or "enter"): ((1, 2), (1, 3))},
    )
    monkeypatch.setattr(reactive_effects, "_age_pulses_in_place", lambda pulses, *, dt: pulses)
    monkeypatch.setattr(
        reactive_effects,
        "build_fade_overlay_into",
        lambda overlay, pulses: overlay.update({(pulse.row, pulse.col): captured_pulses.append((pulse.row, pulse.col)) or 1.0 for pulse in pulses}),
    )
    monkeypatch.setattr(reactive_effects, "build_frame_base_maps", lambda *args, **kwargs: (False, {}, {}))
    monkeypatch.setattr(reactive_effects, "get_engine_overlay_buffer", lambda _engine, _name: {})
    monkeypatch.setattr(reactive_effects, "get_engine_color_map_buffer", lambda _engine, _name: {})
    monkeypatch.setattr(reactive_effects, "render", lambda *args, **kwargs: None)
    monkeypatch.setattr(reactive_effects, "_set_reactive_active_pulse_mix", lambda *args, **kwargs: None)

    run_reactive_fade(engine)

    assert captured_pulses == [(1, 2), (1, 3)]
