from __future__ import annotations

import logging
from threading import Event, RLock, Thread
from typing import Optional

from src.core.effects.device import NullKeyboard, acquire_keyboard

logger = logging.getLogger(__name__)


class _EngineCore:
    """Core engine lifecycle and device acquisition."""

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
        # Reactive typing pulse/highlight intensity (0..50).
        self.reactive_brightness = 25
        self.current_color = (255, 0, 0)  # For static/custom effects
        self.reactive_color: Optional[tuple] = None
        self.reactive_use_manual_color: bool = False
        self.per_key_colors = None
        self.per_key_brightness: Optional[int] = None

        self._brightness_fade_token: int = 0
        self._brightness_fade_lock = RLock()

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
        """Stop current effect."""

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
