#!/usr/bin/env python3
"""KeyRGB Effects Engine.

RGB effects for ITE 8291 keyboards using ite8291r3-ctl library.
"""

from __future__ import annotations

import logging
from threading import Event, RLock, Thread
from typing import Dict, Optional, Tuple

import traceback
from src.core.effects.device import NullKeyboard, acquire_keyboard
from src.core.effects.catalog import (
    ALL_EFFECTS as _ALL_EFFECTS,
    HW_EFFECTS as _HW_EFFECTS,
    SW_EFFECTS as _SW_EFFECTS,
    normalize_effect_name,
)
from src.core.effects.fades import fade_in_per_key, fade_uniform_color
from src.core.effects.hw_payloads import build_hw_effect_payload
from src.core.effects.ite_backend import hw_colors, hw_effects
from src.core.effects.reactive.effects import (
    run_reactive_fade,
    run_reactive_ripple,
)
from src.core.effects.software.effects import (
    run_chase,
    run_color_cycle,
    run_rainbow_swirl,
    run_rainbow_wave,
    run_spectrum_cycle,
    run_strobe,
    run_twinkle,
)
from src.core.effects.timing import clamped_interval, get_interval

logger = logging.getLogger(__name__)


class EffectsEngine:
    """RGB effects engine with hardware and custom effects"""

    # Canonical effect lists are defined in src.core.effects.catalog.
    HW_EFFECTS = _HW_EFFECTS
    SW_EFFECTS = _SW_EFFECTS
    ALL_EFFECTS = _ALL_EFFECTS

    _SW_START_SPECS = {
        # Effect name -> (method_name, fade_to)
        # fade_to: "current" uses self.current_color; otherwise a literal RGB tuple.
        "rainbow_wave": ("_effect_rainbow_wave", (255, 0, 0)),
        "rainbow_swirl": ("_effect_rainbow_swirl", (255, 0, 0)),
        "spectrum_cycle": ("_effect_spectrum_cycle", (255, 0, 0)),
        "color_cycle": ("_effect_color_cycle", (255, 0, 0)),
        "chase": ("_effect_chase", "current"),
        "twinkle": ("_effect_twinkle", "current"),
        "strobe": ("_effect_strobe", "current"),
        "reactive_fade": ("_effect_reactive_fade", "current"),
        "reactive_ripple": ("_effect_reactive_ripple", "current"),
    }

    def __init__(self):
        self.kb_lock = RLock()
        self.device_available = False
        self.kb = NullKeyboard()

        # Attempt to acquire a hardware device, but do not crash if unavailable.
        self._ensure_device_available()
        self.running = False
        self.thread: Optional[Thread] = None
        self.stop_event = Event()

        self.current_effect: Optional[str] = None
        self.speed = 4  # 0-10 (UI speed scale; 10 = fastest)
        self.brightness = 25  # 0-50 (hardware brightness scale)
        self.current_color = (255, 0, 0)  # For static/custom effects
        self.per_key_colors: Optional[Dict[Tuple[int, int], Tuple[int, int, int]]] = None  # For perkey effects

    def _ensure_device_available(self) -> bool:
        """Best-effort attempt to connect to the keyboard device."""

        if self.device_available and not isinstance(self.kb, NullKeyboard):
            return True

        kb, available = acquire_keyboard(kb_lock=self.kb_lock, logger=logger)
        self.kb = kb
        self.device_available = bool(available)
        return self.device_available

    def mark_device_unavailable(self) -> None:
        """Force the engine into a safe 'no device' mode."""

        self.device_available = False
        with self.kb_lock:
            self.kb = NullKeyboard()

    def stop(self):
        """Stop current effect"""
        # Be robust to concurrent callers: treat `self.thread` as a shared
        # pointer and always operate on a local snapshot.
        if not self.running and not self.thread:
            self.current_effect = None
            self.stop_event.clear()
            return

        self.running = False
        self.stop_event.set()

        t = self.thread
        # Clear shared state early so new starts don't race old threads.
        self.thread = None
        self.current_effect = None

        if t:
            t.join(timeout=2.0)
            if t.is_alive():
                # Don't clear the stop event yet; the thread still needs to observe it.
                logger.warning("Effect thread did not stop within timeout")
                return

        self.stop_event.clear()

    def turn_off(self):
        """Turn off all LEDs"""
        self.stop()
        self._ensure_device_available()
        with self.kb_lock:
            self.kb.turn_off()

    def set_brightness(self, brightness: int):
        """Set brightness (0-50 hardware scale)"""
        self.brightness = max(0, min(50, brightness))
        self._ensure_device_available()
        with self.kb_lock:
            self.kb.set_brightness(self.brightness)

    def start_effect(self, effect_name: str, speed: int = 5, brightness: int = 25, color: Optional[tuple] = None):
        """Start an effect (hardware or software)"""
        prev_color = tuple(self.current_color)

        self.stop()

        # If no device is present, keep state but do not crash.
        self._ensure_device_available()

        effect_name = normalize_effect_name(effect_name)

        if effect_name not in self.ALL_EFFECTS:
            raise ValueError(f"Unknown effect: {effect_name}. Valid: {', '.join(self.ALL_EFFECTS)}")

        self.current_effect = effect_name
        self.speed = max(0, min(10, speed))
        self.brightness = max(0, min(50, brightness))

        if color:
            self.current_color = color

        # Hardware effects - delegate to controller
        if effect_name in self.HW_EFFECTS:
            self._start_hw_effect(effect_name)

        # Software effects - run in a worker thread
        else:
            spec = self._SW_START_SPECS.get(effect_name)
            if spec is None:
                # Should not happen due to earlier validation against ALL_EFFECTS.
                raise ValueError(f"Unhandled effect: {effect_name}")

            method_name, fade_to = spec
            if fade_to == "current":
                fade_to_color = tuple(self.current_color)
            else:
                fade_to_color = fade_to

            self._start_sw_effect(
                target=getattr(self, method_name),
                prev_color=prev_color,
                fade_to_color=fade_to_color,
            )

    def _start_sw_effect(
        self,
        *,
        target,
        prev_color: tuple,
        fade_to_color: tuple,
    ) -> None:
        if self.per_key_colors and hasattr(self.kb, "set_key_colors"):
            self._fade_in_per_key(duration_s=0.06)
        else:
            # Fade from previous color to the chosen effect's start color.
            self._fade_uniform_color(
                from_color=prev_color,
                to_color=fade_to_color,
                brightness=int(self.brightness),
                duration_s=0.06,
            )

        self.running = True
        self.thread = Thread(target=target, daemon=True)
        self.thread.start()

    def _start_hw_effect(self, effect_name: str):
        """Start hardware effect"""
        effect_func = hw_effects.get(effect_name)
        if not effect_func:
            raise ValueError(f"Hardware effect not found: {effect_name}")

        effect_data = build_hw_effect_payload(
            effect_name=effect_name,
            effect_func=effect_func,
            ui_speed=int(self.speed),
            brightness=int(self.brightness),
            current_color=tuple(self.current_color),
            hw_colors=hw_colors,
            kb=self.kb,
            kb_lock=self.kb_lock,
            logger=logger,
        )

        with self.kb_lock:
            self.kb.set_effect(effect_data)

    # ===== SOFTWARE EFFECTS =====

    def _get_interval(self, base_ms: int) -> float:
        """Calculate interval based on speed (0-10, 10 = fastest).

        Historically the software effects were effectively capped near the base
        interval even at low speeds. Use the full 1..11x multiplier so speed 0
        is meaningfully slower.
        """

        return get_interval(base_ms, speed=int(self.speed))

    def _clamped_interval(self, base_ms: int, *, min_s: float) -> float:
        return clamped_interval(base_ms, speed=int(self.speed), min_s=float(min_s))

    def _fade_uniform_color(
        self,
        *,
        from_color: tuple,
        to_color: tuple,
        brightness: int,
        duration_s: float,
        steps: int = 18,
    ) -> None:
        """Small cosmetic fade between uniform colors.

        Best-effort only: never raises, never takes too long.
        """

        fade_uniform_color(
            kb=self.kb,
            kb_lock=self.kb_lock,
            from_color=from_color,
            to_color=to_color,
            brightness=brightness,
            duration_s=duration_s,
            steps=steps,
        )

    def _fade_in_per_key(self, *, duration_s: float, steps: int = 12) -> None:
        """Fade in the current per-key map to reduce harsh transitions."""

        fade_in_per_key(
            kb=self.kb,
            kb_lock=self.kb_lock,
            per_key_colors=self.per_key_colors,
            current_color=self.current_color,
            brightness=int(self.brightness),
            duration_s=duration_s,
            steps=steps,
        )

    def _effect_rainbow_wave(self):
        """Rainbow Wave (SW): classic rainbow wave across the keyboard."""
        run_rainbow_wave(self)

    def _effect_rainbow_swirl(self):
        """Rainbow Swirl (SW): swirl around the keyboard center."""
        run_rainbow_swirl(self)

    def _effect_spectrum_cycle(self):
        """Spectrum Cycle (SW): uniform hue cycling."""
        run_spectrum_cycle(self)

    def _effect_color_cycle(self):
        """Color Cycle (SW): smooth RGB cycling."""
        run_color_cycle(self)

    def _effect_chase(self):
        """Chase (SW): moving highlight band."""
        run_chase(self)

    def _effect_twinkle(self):
        """Twinkle (SW): random sparkles."""
        run_twinkle(self)

    def _effect_strobe(self):
        """Strobe (SW): rapid flashing."""
        run_strobe(self)

    def _effect_reactive_fade(self):
        """Reactive Typing (Fade): Best-effort keypress reactive."""
        try:
            run_reactive_fade(self)
        except Exception:
            logger.error("Reactive Fade thread crashed:\n%s", traceback.format_exc())

    def _effect_reactive_ripple(self):
        """Reactive Typing (Ripple): Best-effort keypress reactive."""
        try:
            run_reactive_ripple(self)
        except Exception:
            logger.error("Reactive Ripple thread crashed:\n%s", traceback.format_exc())


if __name__ == "__main__":
    from src.core.effects.demo import run_demo

    run_demo(EffectsEngine)
