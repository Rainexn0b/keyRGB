from __future__ import annotations

import logging
from collections.abc import Mapping
from threading import Event, RLock, Thread
from typing import Any, Callable, Optional

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_KEYBOARD

from src.core.effects.device import NullKeyboard, acquire_keyboard

logger = logging.getLogger(__name__)


class _EngineCore:
    """Core engine lifecycle and device acquisition."""

    def __init__(self, *, backend: Any | None = None) -> None:
        self.backend = backend
        self.kb_lock = RLock()
        self.device_available = False
        self.kb = NullKeyboard()

        # Attempt to acquire a hardware device, but do not crash if unavailable.
        self._ensure_device_available()
        self.running = False
        self.thread: Optional[Thread] = None
        self.stop_event = Event()
        self._thread_generation = 0

        self.current_effect: Optional[str] = None
        self.speed = 4  # 0-10 (UI speed scale; 10 = fastest)
        self.brightness = 25  # 0-50 (hardware brightness scale)
        self.software_effect_target = SOFTWARE_EFFECT_TARGET_KEYBOARD
        self.secondary_software_targets_provider: Callable[[], list[object]] | None = None
        # Reactive typing pulse/highlight intensity (0..50).
        self.reactive_brightness = 25
        self.current_color = (255, 0, 0)  # For static/custom effects
        self.reactive_color: Optional[tuple] = None
        self.reactive_use_manual_color: bool = False
        self.direction: Optional[str] = None
        self.per_key_colors: Mapping[Any, Any] | None = None
        self.per_key_brightness: Optional[int] = None

        # Temporary brightness cap set by idle dim-sync to prevent reactive
        # renders from raising HW brightness above the dim target.
        self._hw_brightness_cap: Optional[int] = None
        # True when temp-dim mode is active (disables brightness-raise in
        # reactive rendering so pulses don't fight dim/restore).
        self._dim_temp_active: bool = False
        # Per-frame brightness stability guard: last brightness actually sent
        # to hardware by the reactive render loop. Used to clamp sudden jumps.
        self._last_rendered_brightness: Optional[int] = None

        # Last brightness passed to enable_user_mode (SET_EFFECT cmd).  Tracked
        # so render() can use the lighter SET_BRIGHTNESS cmd for frame-to-frame
        # brightness changes, avoiding a full mode reinit that flashes the LEDs.
        self._last_hw_mode_brightness: Optional[int] = None

        # Optional render-time transition for reactive temp-dim / restore.
        # The idle-power path updates brightness atomically under kb_lock, then
        # the renderer interpolates toward the target without blocking the loop.
        self._reactive_transition_from_brightness: Optional[int] = None
        self._reactive_transition_to_brightness: Optional[int] = None
        self._reactive_transition_started_at: Optional[float] = None
        self._reactive_transition_duration_s: Optional[float] = None

        # Strength of the currently active reactive pulse frame (0..1). This
        # lets the renderer lift hardware brightness only while a pulse is
        # actually visible, without raising the idle baseline.
        self._reactive_active_pulse_mix: float = 0.0

        self._brightness_fade_token: int = 0
        self._brightness_fade_lock = RLock()

    def _ensure_device_available(self) -> bool:
        """Best-effort attempt to connect to the keyboard device."""

        if self.device_available and not isinstance(self.kb, NullKeyboard):
            return True

        kb, available = acquire_keyboard(kb_lock=self.kb_lock, logger=logger, backend=self.backend)
        self.kb = kb
        self.device_available = bool(available)
        return self.device_available

    def set_backend(self, backend: Any | None) -> None:
        """Update the selected backend and force the next reacquire through it."""

        self.backend = backend
        self.mark_device_unavailable()

    def get_backend_effects(self) -> dict[str, Any]:
        backend = getattr(self, "backend", None)
        effect_fn = getattr(backend, "effects", None) if backend is not None else None
        if not callable(effect_fn):
            return {}
        try:
            raw_effects = effect_fn()
        except Exception:
            return {}
        if not isinstance(raw_effects, dict):
            return {}
        return dict(raw_effects or {})

    def get_backend_colors(self) -> dict[str, Any]:
        backend = getattr(self, "backend", None)
        colors_fn = getattr(backend, "colors", None) if backend is not None else None
        if not callable(colors_fn):
            return {}
        try:
            raw_colors = colors_fn()
        except Exception:
            return {}
        if not isinstance(raw_colors, dict):
            return {}
        return dict(raw_colors or {})

    def mark_device_unavailable(self) -> None:
        """Force the engine into a safe 'no device' mode."""

        self.device_available = False
        with self.kb_lock:
            self.kb = NullKeyboard()

    def stop(self) -> None:
        """Stop current effect."""

        try:
            self._thread_generation = int(getattr(self, "_thread_generation", 0)) + 1
        except Exception:
            self._thread_generation = 1

        # Reset the per-frame brightness guard unconditionally so the next
        # render loop ramps up from 0 instead of jumping to the last rendered
        # brightness.  Without this, restoring from a dim/off state would
        # immediately write at the pre-stop brightness (e.g. 25) on the first
        # frame, bypassing any brightness_override=1 fade-in and making
        # reactive pulses flash at full intensity on wake.
        self._last_rendered_brightness = None
        # Force the next render frame to re-init user mode via SET_EFFECT.
        self._last_hw_mode_brightness = None
        self._reactive_transition_from_brightness = None
        self._reactive_transition_to_brightness = None
        self._reactive_transition_started_at = None
        self._reactive_transition_duration_s = None
        self._reactive_active_pulse_mix = 0.0

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
