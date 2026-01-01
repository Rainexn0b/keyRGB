#!/usr/bin/env python3
"""KeyRGB Effects Engine.

RGB effects for ITE 8291 keyboards using ite8291r3-ctl library.
"""

from __future__ import annotations

import logging
import colorsys
from threading import Event, RLock, Thread
from typing import Dict, Optional, Tuple

from src.core.effects.device import NullKeyboard, acquire_keyboard
from src.core.effects.fades import fade_in_per_key, fade_uniform_color
from src.core.effects.hw_payloads import build_hw_effect_payload
from src.core.effects.ite_backend import hw_colors, hw_effects
from src.core.effects.software_loops import (
    run_fire,
    run_perkey_breathing,
    run_perkey_pulse,
    run_pulse,
    run_random,
    run_strobe,
)
from src.core.effects.timing import brightness_factor, clamped_interval, get_interval

logger = logging.getLogger(__name__)

# Backwards-compatibility: older code/tests import `_NullKeyboard` from this module.
_NullKeyboard = NullKeyboard



class EffectsEngine:
    """RGB effects engine with hardware and custom effects"""
    
    # Hardware effects (built into the controller)
    HW_EFFECTS = ['rainbow', 'breathing', 'wave', 'ripple', 'marquee', 'raindrop', 'aurora', 'fireworks']
    
    # Custom software effects
    SW_EFFECTS = ['static', 'pulse', 'strobe', 'fire', 'random', 'perkey_breathing', 'perkey_pulse']
    
    ALL_EFFECTS = HW_EFFECTS + SW_EFFECTS
    
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
        if self.running:
            self.running = False
            self.stop_event.set()
            if self.thread:
                self.thread.join(timeout=2.0)
                if self.thread.is_alive():
                    # Don't clear the stop event yet; the thread still needs to observe it.
                    logger.warning("Effect thread did not stop within timeout")
                else:
                    self.thread = None
                    self.current_effect = None
                    self.stop_event.clear()
            else:
                self.current_effect = None
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
        prev_brightness = int(getattr(self, "brightness", 25) or 0)

        self.stop()

        # If no device is present, keep state but do not crash.
        self._ensure_device_available()
        
        effect_name = effect_name.lower()
        
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
        
        # Software effects - run in thread
        elif effect_name == 'static':
            self._fade_uniform_color(
                from_color=prev_color,
                to_color=tuple(self.current_color),
                brightness=int(self.brightness),
                duration_s=0.12,
            )
        
        elif effect_name == 'pulse':
            self._fade_uniform_color(
                from_color=prev_color,
                to_color=tuple(self.current_color),
                brightness=int(self.brightness),
                duration_s=0.10,
            )
            self.running = True
            self.thread = Thread(target=self._effect_pulse, daemon=True)
            self.thread.start()
        
        elif effect_name == 'strobe':
            # Ease into strobe so it doesn't feel like a harsh snap.
            self._fade_uniform_color(
                from_color=prev_color,
                to_color=(255, 255, 255),
                brightness=int(self.brightness),
                duration_s=0.08,
            )
            self.running = True
            self.thread = Thread(target=self._effect_strobe, daemon=True)
            self.thread.start()
        
        elif effect_name == 'fire':
            # Start fire from a warm base tone.
            self._fade_uniform_color(
                from_color=prev_color,
                to_color=(255, 80, 0),
                brightness=int(self.brightness),
                duration_s=0.08,
            )
            self.running = True
            self.thread = Thread(target=self._effect_fire, daemon=True)
            self.thread.start()
        
        elif effect_name == 'random':
            # Fade into the first random frame to reduce "flash".
            self._fade_uniform_color(
                from_color=prev_color,
                to_color=tuple(self.current_color),
                brightness=int(self.brightness),
                duration_s=0.06,
            )
            self.running = True
            self.thread = Thread(target=self._effect_random, daemon=True)
            self.thread.start()
        
        elif effect_name == 'perkey_breathing':
            self._fade_in_per_key(duration_s=0.12)
            self.running = True
            self.thread = Thread(target=self._effect_perkey_breathing, daemon=True)
            self.thread.start()
        
        elif effect_name == 'perkey_pulse':
            self._fade_in_per_key(duration_s=0.10)
            self.running = True
            self.thread = Thread(target=self._effect_perkey_pulse, daemon=True)
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
    
    def _hsv_to_rgb(self, h: float, s: float, v: float) -> tuple:
        """Convert HSV to RGB (h: 0-1, s: 0-1, v: 0-1)"""
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return (int(r * 255), int(g * 255), int(b * 255))
    
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
    
    def _brightness_factor(self) -> float:
        """Get brightness as 0-1 factor"""
        return brightness_factor(int(self.brightness))
    
    def _effect_pulse(self):
        """Pulse: Rhythmic brightness pulses with current color"""
        run_pulse(self)
    
    def _effect_strobe(self):
        """Strobe: Rapid on/off flashing"""
        run_strobe(self)
    
    def _effect_fire(self):
        """Fire: Flickering red/orange flames"""
        run_fire(self)
    
    def _effect_random(self):
        """Random: Random color changes"""
        run_random(self)
    
    def _effect_perkey_breathing(self):
        """Per-Key Breathing: Breathing animation that preserves each key's individual color"""
        run_perkey_breathing(self)
    
    def _effect_perkey_pulse(self):
        """Per-Key Pulse: Pulse animation that preserves each key's individual color"""
        run_perkey_pulse(self)


if __name__ == '__main__':
    from src.core.effects.demo import run_demo

    run_demo(EffectsEngine)
