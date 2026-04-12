from __future__ import annotations

import logging
import os
import time
from threading import RLock
from typing import Callable

from ..device import KeyboardDeviceProtocol
from ..transitions import choose_steps

logger = logging.getLogger("src.core.effects.engine_brightness")

_INT_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_INT_ATTR_ERRORS = (AttributeError,) + _INT_COERCION_ERRORS
_BRIGHTNESS_FADE_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _debug_brightness_enabled() -> bool:
    return os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1"


def _brightness_fade_token_or_default(engine: "_EngineBrightness", *, default: int) -> int:
    try:
        return int(engine._brightness_fade_token)
    except AttributeError:
        return default


def _device_available_or_default(engine: "_EngineBrightness", *, default: bool) -> bool:
    try:
        return bool(engine.device_available)
    except AttributeError:
        return default


class _EngineBrightness:
    """Brightness state + best-effort fades."""

    kb_lock: RLock
    kb: KeyboardDeviceProtocol
    device_available: bool
    brightness: int
    stop: Callable[[], None]
    _ensure_device_available: Callable[[], bool]

    _brightness_fade_token: int
    _brightness_fade_lock: RLock

    def _advance_brightness_fade_token_unlocked(self) -> int:
        current_token = _brightness_fade_token_or_default(self, default=0)
        next_token = current_token + 1
        self._brightness_fade_token = next_token
        return next_token

    def _bump_brightness_fade_token(self) -> int:
        try:
            with self._brightness_fade_lock:
                return self._advance_brightness_fade_token_unlocked()
        except (RuntimeError, OSError):
            logger.exception("Failed to advance brightness fade token under lock")

        try:
            return self._advance_brightness_fade_token_unlocked()
        except _INT_ATTR_ERRORS:
            logger.exception("Failed to advance brightness fade token")
            return -1

    def _fade_brightness(
        self,
        *,
        start: int,
        end: int,
        apply_to_hardware: bool,
        duration_s: float,
        token: int,
        max_steps: int = 30,
    ) -> None:
        """Best-effort brightness fade.

        Uses small stepped updates to reduce abrupt off/dim transitions.
        Never raises.
        """

        try:
            s = max(0, min(50, int(start)))
            e = max(0, min(50, int(end)))
            if e == s:
                return

            if duration_s <= 0:
                steps = 1
                dt = 0.0
            else:
                steps = choose_steps(duration_s=float(duration_s), max_steps=int(max_steps), target_fps=60.0)
                steps = max(2, int(steps))
                dt = float(duration_s) / float(steps)

            if apply_to_hardware:
                self._ensure_device_available()

            for i in range(1, steps + 1):
                try:
                    if int(token) != int(self._brightness_fade_token):
                        return
                except _INT_ATTR_ERRORS:
                    logger.exception("Failed to compare brightness fade token")
                    return
                t = float(i) / float(steps)
                val = int(round(s + (e - s) * t))
                if val == s:
                    continue
                with self.kb_lock:
                    self.brightness = val
                    if apply_to_hardware:
                        self.kb.set_brightness(int(val))
                if dt > 0:
                    time.sleep(dt)
        except _BRIGHTNESS_FADE_RUNTIME_ERRORS:
            logger.exception("Brightness fade failed")
            return

    def turn_off(self, *, fade: bool = False, fade_duration_s: float = 0.18) -> None:
        """Turn off all LEDs."""

        token = self._bump_brightness_fade_token()

        self.stop()
        self._ensure_device_available()

        if fade:
            try:
                prev = int(self.brightness)
            except _INT_ATTR_ERRORS:
                prev = 0

            if prev > 1:
                self._fade_brightness(
                    start=prev,
                    end=1,
                    apply_to_hardware=True,
                    duration_s=float(fade_duration_s),
                    token=token,
                    max_steps=20,
                )

        with self.kb_lock:
            try:
                self.brightness = 0
            except _INT_ATTR_ERRORS:
                logger.exception("Failed to update engine brightness cache during turn_off")
            self.kb.turn_off()

    def set_brightness(
        self,
        brightness: int,
        *,
        apply_to_hardware: bool = True,
        fade: bool = False,
        fade_duration_s: float = 0.18,
    ) -> None:
        """Set brightness (0-50 hardware scale)."""

        token = self._bump_brightness_fade_token()
        target = max(0, min(50, int(brightness)))

        try:
            prev = int(self.brightness)
        except _INT_ATTR_ERRORS:
            prev = 0

        if fade and target != prev:
            end = 1 if target == 0 and prev > 1 else target
            self._fade_brightness(
                start=prev,
                end=end,
                apply_to_hardware=bool(apply_to_hardware),
                duration_s=float(fade_duration_s),
                token=token,
                max_steps=30,
            )

        with self.kb_lock:
            try:
                prev = int(self.brightness)
            except _INT_ATTR_ERRORS:
                prev = prev

            self.brightness = int(target)

            if _debug_brightness_enabled():
                logger.info(
                    "engine.set_brightness: prev=%s new=%s apply_to_hardware=%s device_available=%s",
                    prev,
                    self.brightness,
                    bool(apply_to_hardware),
                    _device_available_or_default(self, default=False),
                )

            if not apply_to_hardware:
                return

            self._ensure_device_available()
            if _debug_brightness_enabled():
                logger.info("engine -> kb.set_brightness: %s", self.brightness)
            self.kb.set_brightness(self.brightness)
