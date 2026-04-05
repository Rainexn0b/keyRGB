from __future__ import annotations

import logging
from threading import Event, RLock, Thread
from typing import Callable, Protocol, cast

from ..device import (
    Color,
    KeyboardBackendProtocol,
    KeyboardDeviceProtocol,
    NullKeyboard,
    PerKeyColorMap,
    acquire_keyboard,
)
from ..software_targets import SOFTWARE_EFFECT_TARGET_KEYBOARD

logger = logging.getLogger("src.core.effects.engine_core")

HardwareEffectBuilder = Callable[..., object]


class _EffectsBackendProtocol(KeyboardBackendProtocol, Protocol):
    name: str

    def effects(self) -> dict[str, HardwareEffectBuilder]: ...

    def colors(self) -> dict[str, object]: ...


def _backend_effects_method_or_none(backend: object | None) -> Callable[[], object] | None:
    if backend is None:
        return None
    try:
        effect_fn = backend.effects  # type: ignore[attr-defined]
    except AttributeError:
        return None
    return cast(Callable[[], object] | None, effect_fn if callable(effect_fn) else None)


def _backend_colors_method_or_none(backend: object | None) -> Callable[[], object] | None:
    if backend is None:
        return None
    try:
        colors_fn = backend.colors  # type: ignore[attr-defined]
    except AttributeError:
        return None
    return cast(Callable[[], object] | None, colors_fn if callable(colors_fn) else None)


def _backend_name(backend: object | None) -> str:
    if backend is None:
        return "NoneType"
    try:
        name = backend.name  # type: ignore[attr-defined]
    except AttributeError:
        return type(backend).__name__
    return str(name)


def _thread_generation_or_default(engine: "_EngineCore", *, default: int) -> int:
    try:
        return int(engine._thread_generation)
    except AttributeError:
        return default


class _EngineCore:
    """Core engine lifecycle and device acquisition."""

    def __init__(self, *, backend: _EffectsBackendProtocol | None = None) -> None:
        self.backend = backend
        self.kb_lock = RLock()
        self.device_available = False
        self.kb: KeyboardDeviceProtocol = NullKeyboard()

        self._ensure_device_available()
        self.running = False
        self.thread: Thread | None = None
        self.stop_event = Event()
        self._thread_generation = 0

        self.current_effect: str | None = None
        self.speed = 4
        self.brightness = 25
        self.software_effect_target = SOFTWARE_EFFECT_TARGET_KEYBOARD
        self.secondary_software_targets_provider: Callable[[], list[object]] | None = None
        self.reactive_brightness = 25
        self.current_color: Color = (255, 0, 0)
        self.reactive_color: Color | None = None
        self.reactive_use_manual_color: bool = False
        self.direction: str | None = None
        self.per_key_colors: PerKeyColorMap | None = None
        self.per_key_brightness: int | None = None

        self._hw_brightness_cap: int | None = None
        self._dim_temp_active: bool = False
        self._last_rendered_brightness: int | None = None
        self._last_hw_mode_brightness: int | None = None

        self._reactive_transition_from_brightness: int | None = None
        self._reactive_transition_to_brightness: int | None = None
        self._reactive_transition_started_at: float | None = None
        self._reactive_transition_duration_s: float | None = None

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

    def set_backend(self, backend: _EffectsBackendProtocol | None) -> None:
        """Update the selected backend and force the next reacquire through it."""

        self.backend = backend
        self.mark_device_unavailable()

    def get_backend_effects(self) -> dict[str, HardwareEffectBuilder]:
        backend = self.backend
        effect_fn = _backend_effects_method_or_none(backend)
        if not callable(effect_fn):
            return {}
        backend_name = _backend_name(backend)
        try:
            raw_effects = effect_fn()
        except Exception:  # @quality-exception exception-transparency: backend effect discovery is a runtime plugin boundary and engine behavior must degrade to no backend effects
            logger.exception("Failed to query backend effects from '%s'", backend_name)
            return {}
        if not isinstance(raw_effects, dict):
            return {}
        return dict(raw_effects or {})

    def get_backend_colors(self) -> dict[str, object]:
        backend = self.backend
        colors_fn = _backend_colors_method_or_none(backend)
        if not callable(colors_fn):
            return {}
        backend_name = _backend_name(backend)
        try:
            raw_colors = colors_fn()
        except Exception:  # @quality-exception exception-transparency: backend color discovery is a runtime plugin boundary and engine behavior must degrade to no backend colors
            logger.exception("Failed to query backend colors from '%s'", backend_name)
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
            self._thread_generation = _thread_generation_or_default(self, default=0) + 1
        except (TypeError, ValueError, OverflowError):
            self._thread_generation = 1

        self._last_rendered_brightness = None
        self._last_hw_mode_brightness = None
        self._reactive_transition_from_brightness = None
        self._reactive_transition_to_brightness = None
        self._reactive_transition_started_at = None
        self._reactive_transition_duration_s = None
        self._reactive_active_pulse_mix = 0.0

        if not self.running and not self.thread:
            self.current_effect = None
            self.stop_event.clear()
            return

        self.running = False
        self.stop_event.set()

        thread = self.thread
        self.thread = None
        self.current_effect = None

        if thread:
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning("Effect thread did not stop within timeout")
                return

        self.stop_event.clear()
