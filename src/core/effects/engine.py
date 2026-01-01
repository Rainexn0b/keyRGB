#!/usr/bin/env python3
"""KeyRGB Effects Engine.

RGB effects for ITE 8291 keyboards using ite8291r3-ctl library.
"""

from __future__ import annotations

import logging
import colorsys
import time
from threading import Event, RLock, Thread
from typing import Dict, Optional, Tuple

from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS, get, hw_colors, hw_effects
from src.core.effects.perkey_animation import (
    build_full_color_grid,
    enable_user_mode_once,
)
from src.core.effects.software_loops import (
    run_fire,
    run_perkey_breathing,
    run_perkey_pulse,
    run_pulse,
    run_random,
    run_strobe,
)
from src.core.effects.transitions import avoid_full_black, choose_steps, scaled_color_map_nonzero

from src.core.logging_utils import log_throttled


logger = logging.getLogger(__name__)



class _NullKeyboard:
    """Fallback keyboard implementation used when no device is available."""

    def turn_off(self) -> None:
        return

    def set_brightness(self, _brightness: int) -> None:
        return

    def set_color(self, _color, *, brightness: int):
        return

    def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = True):
        return

    def set_effect(self, _effect_data) -> None:
        return

    def set_palette_color(self, _slot: int, _color) -> None:
        return

    def get_brightness(self) -> int:
        return 0

    def is_off(self) -> bool:
        return True



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
        self.kb = _NullKeyboard()

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

        if self.device_available and not isinstance(self.kb, _NullKeyboard):
            return True

        try:
            with self.kb_lock:
                self.kb = get()
            self.device_available = True
            return True
        except FileNotFoundError:
            self.mark_device_unavailable()
            return False
        except Exception as exc:
            # Avoid log spam, but do surface the root cause in debug logs.
            log_throttled(
                logger,
                "effects.ensure_device_available",
                interval_s=60,
                level=logging.DEBUG,
                msg="Failed to acquire keyboard device; falling back to NullKeyboard",
                exc=exc,
            )
            self.mark_device_unavailable()
            return False

    def mark_device_unavailable(self) -> None:
        """Force the engine into a safe 'no device' mode."""

        self.device_available = False
        with self.kb_lock:
            self.kb = _NullKeyboard()
    
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

        def _allowed_keys(fn) -> set[str]:
            """Best-effort introspection of ite8291r3-ctl's effect builders."""
            try:
                freevars = getattr(fn, "__code__").co_freevars
                closure = getattr(fn, "__closure__")
                if not freevars or not closure:
                    return set()
                mapping = dict(zip(freevars, [c.cell_contents for c in closure]))
                args = mapping.get("args")
                if isinstance(args, dict):
                    return set(args.keys())
            except Exception as exc:
                log_throttled(
                    logger,
                    "legacy.effects.allowed_keys",
                    interval_s=120,
                    level=logging.DEBUG,
                    msg="Failed to introspect hardware effect args",
                    exc=exc,
                )
            return set()

        # The controller's speed scale is inverted compared to the UX:
        # UI: 10 = fastest, 0/1 = slowest
        # HW: larger values slow the effect down
        hw_speed = max(0, min(10, 11 - int(self.speed)))

        # Build kwargs, then filter to what this effect actually supports.
        hw_kwargs = {
            "speed": hw_speed,
            "brightness": self.brightness,
        }

        # For breathing, use the user's configured RGB.
        # The controller expects a palette index, so we program a palette slot
        # and then reference it.
        if effect_name == "breathing":
            palette_slot = hw_colors.get("red", 1)
            try:
                with self.kb_lock:
                    # Slot must be 1..7 and takes an (r,g,b) tuple.
                    self.kb.set_palette_color(palette_slot, tuple(self.current_color))
            except Exception:
                # If palette programming fails, we'll still request the slot.
                log_throttled(
                    logger,
                    "legacy.effects.palette_color",
                    interval_s=120,
                    level=logging.DEBUG,
                    msg="Failed to program palette slot for breathing effect",
                )
            hw_kwargs["color"] = palette_slot

        allowed = _allowed_keys(effect_func)
        if allowed:
            hw_kwargs = {k: v for k, v in hw_kwargs.items() if k in allowed}

        # Some vendored effects (e.g. rainbow) do not accept all common kwargs.
        # If introspection fails or the effect builder changes, retry by removing
        # the specific unsupported key mentioned in the error.
        last_err = None
        for _ in range(4):
            try:
                effect_data = effect_func(**hw_kwargs)
                break
            except ValueError as e:
                msg = str(e)
                last_err = e
                # Expect errors like: "'speed' attr is not needed by effect"
                if "attr is not needed" in msg and msg.startswith("'"):
                    bad = msg.split("'", 2)[1]
                    if bad in hw_kwargs:
                        hw_kwargs.pop(bad, None)
                        continue
                raise
        else:
            raise RuntimeError("Failed to build hardware effect payload") from last_err
        
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

        speed_factor = max(1, min(11, 11 - int(self.speed)))

        # Global slowdown for software effects.
        # Tuned by feel: low UI speeds (e.g. 2) should be noticeably slow.
        slowdown = 1.89

        return (base_ms * float(speed_factor) * float(slowdown)) / 1000.0

    def _clamped_interval(self, base_ms: int, *, min_s: float) -> float:
        interval = self._get_interval(base_ms)
        return max(float(min_s), float(interval))

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

        try:
            if duration_s <= 0:
                steps = 1
                dt = 0.0
            else:
                steps = choose_steps(duration_s=float(duration_s), max_steps=int(steps))
                dt = float(duration_s) / float(steps)

            fr, fg, fb = (int(from_color[0]), int(from_color[1]), int(from_color[2]))
            tr, tg, tb = (int(to_color[0]), int(to_color[1]), int(to_color[2]))
            brightness = max(0, min(50, int(brightness)))

            # Avoid brightness 0 during transitions (tray/hardware pollers may interpret it as "off").
            effective_brightness = max(1, brightness) if brightness > 0 else 0

            for i in range(1, steps + 1):
                t = float(i) / float(steps)
                r = int(round(fr + (tr - fr) * t))
                g = int(round(fg + (tg - fg) * t))
                b = int(round(fb + (tb - fb) * t))

                r, g, b = avoid_full_black(
                    rgb=(r, g, b),
                    target_rgb=(tr, tg, tb),
                    brightness=effective_brightness,
                )
                with self.kb_lock:
                    self.kb.set_color((r, g, b), brightness=effective_brightness)
                if dt > 0:
                    time.sleep(dt)
        except Exception:
            return

    def _fade_in_per_key(self, *, duration_s: float, steps: int = 12) -> None:
        """Fade in the current per-key map to reduce harsh transitions."""

        try:
            if duration_s <= 0:
                return
            if not self.per_key_colors:
                return

            steps = choose_steps(duration_s=float(duration_s), max_steps=int(steps), target_fps=50.0, min_dt_s=0.012)
            dt = float(duration_s) / float(steps)

            full_colors = build_full_color_grid(
                base_color=tuple(int(x) for x in (self.current_color or (255, 0, 0))),
                per_key_colors=self.per_key_colors,
                num_rows=NUM_ROWS,
                num_cols=NUM_COLS,
            )

            enable_user_mode_once(kb=self.kb, kb_lock=self.kb_lock, brightness=self.brightness)

            for i in range(1, steps + 1):
                scale = float(i) / float(steps)
                color_map = scaled_color_map_nonzero(full_colors, scale=scale, brightness=int(self.brightness))
                with self.kb_lock:
                    self.kb.set_key_colors(color_map, brightness=int(self.brightness), enable_user_mode=False)
                time.sleep(dt)
        except Exception:
            return
    
    def _brightness_factor(self) -> float:
        """Get brightness as 0-1 factor"""
        return self.brightness / 50.0
    
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
    # Test mode
    print("KeyRGB Effects Test Mode")
    print("Press Ctrl+C to exit")
    
    engine = EffectsEngine()
    
    try:
        print("\nTesting hardware effects...")
        for effect in ['rainbow', 'breathing', 'wave']:
            print(f"  {effect}")
            engine.start_effect(effect, speed=5, brightness=25)
            time.sleep(4)
        
        print("\nTesting software effects...")
        for effect in ['static', 'pulse', 'fire']:
            print(f"  {effect}")
            engine.start_effect(effect, speed=5, brightness=25, color=(255, 0, 0))
            time.sleep(4)
        
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        engine.stop()
        engine.turn_off()
        print("Done!")
