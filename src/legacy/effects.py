#!/usr/bin/env python3
"""KeyRGB Effects Engine.

RGB effects for ITE 8291 keyboards using ite8291r3-ctl library.
"""

from src.legacy.ite_backend import NUM_COLS, NUM_ROWS, get, hw_colors, hw_effects
from src.legacy.perkey_animation import (
    build_full_color_grid,
    enable_user_mode_once,
    load_per_key_colors_from_config,
    scaled_color_map,
)

import time
import math
import colorsys
from threading import Thread, Event, RLock
from typing import Optional, Dict, Tuple



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
            self.device_available = False
            self.kb = _NullKeyboard()
            return False
        except Exception:
            self.device_available = False
            self.kb = _NullKeyboard()
            return False
    
    def stop(self):
        """Stop current effect"""
        if self.running:
            self.running = False
            self.stop_event.set()
            if self.thread:
                self.thread.join(timeout=2.0)
            self.thread = None
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
            with self.kb_lock:
                self.kb.set_color(self.current_color, brightness=self.brightness)
        
        elif effect_name == 'pulse':
            self.running = True
            self.thread = Thread(target=self._effect_pulse, daemon=True)
            self.thread.start()
        
        elif effect_name == 'strobe':
            self.running = True
            self.thread = Thread(target=self._effect_strobe, daemon=True)
            self.thread.start()
        
        elif effect_name == 'fire':
            self.running = True
            self.thread = Thread(target=self._effect_fire, daemon=True)
            self.thread.start()
        
        elif effect_name == 'random':
            self.running = True
            self.thread = Thread(target=self._effect_random, daemon=True)
            self.thread.start()
        
        elif effect_name == 'perkey_breathing':
            self.running = True
            self.thread = Thread(target=self._effect_perkey_breathing, daemon=True)
            self.thread.start()
        
        elif effect_name == 'perkey_pulse':
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
            except Exception:
                pass
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
                pass
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
        """Calculate interval based on speed (0-10, inverted for consistency)"""
        speed_factor = (11 - self.speed) / 10.0  # Invert: 10=fast, 0=slow
        return (base_ms * speed_factor) / 1000.0
    
    def _brightness_factor(self) -> float:
        """Get brightness as 0-1 factor"""
        return self.brightness / 50.0
    
    def _effect_pulse(self):
        """Pulse: Rhythmic brightness pulses with current color"""
        phase = 0.0
        interval = self._get_interval(300)
        
        while self.running:
            # Keep "user mode" on and modulate brightness rather than RGB to
            # avoid the library treating black as "off" and flipping state.
            pulse = (math.sin(phase) + 1) / 2  # 0-1
            pulse_brightness = int(round(self.brightness * pulse))
            # Avoid 0 during software animation: 0 is interpreted as "off" by
            # the tray hardware poller and can cause flicker.
            pulse_brightness = max(1, min(self.brightness, pulse_brightness))

            with self.kb_lock:
                self.kb.set_color(self.current_color, brightness=pulse_brightness)

            phase += 0.1
            time.sleep(interval)
    
    def _effect_strobe(self):
        """Strobe: Rapid on/off flashing"""
        on = False
        interval = max(0.1, self._get_interval(100))
        
        while self.running:
            with self.kb_lock:
                if on:
                    self.kb.set_color((255, 255, 255), brightness=self.brightness)
                else:
                    # Use black instead of turn_off() so we don't drive
                    # hardware brightness to 0 (which the tray treats as "off").
                    self.kb.set_color((0, 0, 0), brightness=max(1, self.brightness))

            on = not on
            time.sleep(interval)
    
    def _effect_fire(self):
        """Fire: Flickering red/orange flames"""
        import random
        interval = max(0.1, self._get_interval(200))
        
        while self.running:
            factor = self._brightness_factor()
            r = int((200 + random.random() * 55) * factor)
            g = int((random.random() * 100) * factor)
            b = 0

            with self.kb_lock:
                self.kb.set_color((r, g, b), brightness=self.brightness)
            time.sleep(interval)
    
    def _effect_random(self):
        """Random: Random color changes"""
        import random
        interval = max(0.3, self._get_interval(800))
        
        while self.running:
            factor = self._brightness_factor()
            r = int(random.random() * 255 * factor)
            g = int(random.random() * 255 * factor)
            b = int(random.random() * 255 * factor)

            with self.kb_lock:
                self.kb.set_color((r, g, b), brightness=self.brightness)
            time.sleep(interval)
    
    def _effect_perkey_breathing(self):
        """Per-Key Breathing: Breathing animation that preserves each key's individual color"""
        phase = 0.0
        # Breathing should feel slow/smooth but still obviously animated.
        # Using a smaller base interval avoids the "looks static" problem at
        # mid/low UI speeds.
        interval = max(0.03, self._get_interval(120))
        
        # Load per-key colors if not already set
        if not self.per_key_colors:
            self.per_key_colors = load_per_key_colors_from_config()
        
        # If no per-key colors configured, fall back to uniform breathing
        if not self.per_key_colors:
            self._effect_pulse()
            return
        
        # IMPORTANT:
        # - `set_key_colors(..., enable_user_mode=True)` calls `enable_user_mode()` internally.
        #   Doing that every frame causes visible flicker/flash on some firmware.
        # - `set_key_colors()` writes a full 6x16 frame buffer. Any key missing from
        #   `color_map` becomes black. If the saved per-key map is sparse, that looks
        #   like erratic flashing. We therefore fill missing keys with the base color.
        full_colors = build_full_color_grid(
            base_color=tuple(int(x) for x in (self.current_color or (255, 0, 0))),
            per_key_colors=self.per_key_colors,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
        )

        enable_user_mode_once(kb=self.kb, kb_lock=self.kb_lock, brightness=self.brightness)

        while self.running:
            # Calculate breathing factor (0.2 to 1.0 to avoid going too dim)
            breath = (math.sin(phase) + 1.0) / 2.0  # 0..1
            # Smooth curve (ease-in/out) so it feels like "breathing".
            breath = breath * breath * (3.0 - 2.0 * breath)  # smoothstep
            breath = 0.15 + breath * 0.85  # 0.15..1.0
            
            color_map = scaled_color_map(full_colors, scale=breath)
            
            with self.kb_lock:
                self.kb.set_key_colors(color_map, enable_user_mode=False)
            
            phase += 0.20
            time.sleep(interval)
    
    def _effect_perkey_pulse(self):
        """Per-Key Pulse: Pulse animation that preserves each key's individual color"""
        phase = 0.0
        # Pulse is intentionally more "snappy" than breathing.
        interval = max(0.02, self._get_interval(90))
        
        # Load per-key colors if not already set
        if not self.per_key_colors:
            self.per_key_colors = load_per_key_colors_from_config()
        
        # If no per-key colors configured, fall back to uniform pulse
        if not self.per_key_colors:
            self._effect_pulse()
            return
        
        full_colors = build_full_color_grid(
            base_color=tuple(int(x) for x in (self.current_color or (255, 0, 0))),
            per_key_colors=self.per_key_colors,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
        )

        enable_user_mode_once(kb=self.kb, kb_lock=self.kb_lock, brightness=self.brightness)

        while self.running:
            # Calculate pulse factor (sharper than breathing)
            pulse = (math.sin(phase) + 1.0) / 2.0  # 0..1
            # Make it much sharper than breathing (quick "thump").
            pulse = pulse ** 3
            pulse = 0.08 + pulse * 0.92  # 0.08..1.0
            
            color_map = scaled_color_map(full_colors, scale=pulse)
            
            with self.kb_lock:
                self.kb.set_key_colors(color_map, enable_user_mode=False)
            
            phase += 0.35
            time.sleep(interval)


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
