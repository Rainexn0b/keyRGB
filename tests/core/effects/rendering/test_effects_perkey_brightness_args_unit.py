from __future__ import annotations

from threading import RLock

import pytest

from src.core.effects.device import NullKeyboard
from src.core.effects.fades import fade_in_per_key
from src.core.effects.engine import EffectsEngine


def test_perkey_fade_passes_brightness_kwarg() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.calls: list[dict] = []

        def enable_user_mode(self, *, brightness: int, save: bool):
            self.calls.append(
                {
                    "fn": "enable_user_mode",
                    "brightness": int(brightness),
                    "save": bool(save),
                }
            )

        def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
            # This signature matches the core backend protocol.
            self.calls.append(
                {
                    "fn": "set_key_colors",
                    "brightness": int(brightness),
                    "enable_user_mode": bool(enable_user_mode),
                    "count": len(color_map),
                }
            )

    engine = EffectsEngine()
    spy = SpyKeyboard()

    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.brightness = 25
    engine.current_color = (255, 0, 0)
    engine.per_key_colors = {(0, 0): (255, 0, 0)}

    engine._fade_in_per_key(duration_s=0.01, steps=3)

    assert any(c["fn"] == "enable_user_mode" for c in spy.calls)
    set_calls = [c for c in spy.calls if c["fn"] == "set_key_colors"]
    assert set_calls
    assert all(c["brightness"] == 25 for c in set_calls)


def test_perkey_fade_ignores_invalid_brightness_values() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.calls: list[dict] = []

        def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
            self.calls.append(
                {
                    "brightness": int(brightness),
                    "enable_user_mode": bool(enable_user_mode),
                    "count": len(color_map),
                }
            )

    spy = SpyKeyboard()

    fade_in_per_key(
        kb=spy,
        kb_lock=RLock(),
        per_key_colors={(0, 0): (255, 0, 0)},
        current_color=(255, 0, 0),
        brightness="bad",
        duration_s=0.01,
        steps=3,
    )

    assert spy.calls == []


def test_perkey_fade_propagates_unexpected_set_key_colors_errors() -> None:
    class BrokenKeyboard(NullKeyboard):
        def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
            del color_map, brightness, enable_user_mode
            raise LookupError("unexpected per-key fade bug")

    engine = EffectsEngine()

    engine.kb = BrokenKeyboard()
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.brightness = 25
    engine.current_color = (255, 0, 0)
    engine.per_key_colors = {(0, 0): (255, 0, 0)}

    with pytest.raises(LookupError, match="unexpected per-key fade bug"):
        engine._fade_in_per_key(duration_s=0.01, steps=3)
