from __future__ import annotations

import os
import random
import threading
import time

from src.core.effects.engine import EffectsEngine
from src.core.effects.software_loops import run_chase, run_reactive_fade


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

    old = os.environ.get("KEYRGB_DISABLE_EVDEV")
    os.environ["KEYRGB_DISABLE_EVDEV"] = "1"

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
        if old is None:
            os.environ.pop("KEYRGB_DISABLE_EVDEV", None)
        else:
            os.environ["KEYRGB_DISABLE_EVDEV"] = old

    calls = engine.kb.calls
    assert len(calls) >= 3
    assert len(set(calls)) >= 2
