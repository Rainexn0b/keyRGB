from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event, RLock, Thread
from typing import Protocol, TypeVar, cast

from keyrgb.core.backends.base import BackendCapabilities, normalize_backend_capabilities

from ..device import (
    Color,
    KeyboardBackendProtocol,
    KeyboardDeviceProtocol,
    NullKeyboard,
    PerKeyColorMap,
    acquire_keyboard,
)
from ..matrix_layout import (
    EffectGridGeometry,
    effect_geometry_from_dimensions,
    reference_effect_geometry,
)
from ..reactive._reactive_restore_seed import apply_queued_reactive_restore_seed
from ..reactive._render_brightness_support import ReactiveRenderState
from ..software_targets import SOFTWARE_EFFECT_TARGET_KEYBOARD

logger = logging.getLogger("keyrgb.core.effects.engine_core")
_BACKEND_DISCOVERY_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)

HardwareEffectBuilder = Callable[..., object]
_BackendDiscoveryValue = TypeVar("_BackendDiscoveryValue")


class _EffectsBackendProtocol(KeyboardBackendProtocol, Protocol):
    name: str

    def capabilities(self) -> BackendCapabilities: ...

    def dimensions(self) -> tuple[int, int]: ...

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


def _backend_capabilities(backend: object | None) -> BackendCapabilities:
    if backend is None:
        return normalize_backend_capabilities(None)
    capabilities_fn = getattr(backend, "capabilities", None)
    if not callable(capabilities_fn):
        return normalize_backend_capabilities(None)
    try:
        return normalize_backend_capabilities(capabilities_fn())
    except _BACKEND_DISCOVERY_ERRORS:
        logger.exception("Failed to query backend capabilities from '%s'", _backend_name(backend))
        return normalize_backend_capabilities(None)


def _backend_effect_geometry(backend: object | None, *, capabilities: BackendCapabilities) -> EffectGridGeometry:
    backend_name = None if backend is None else _backend_name(backend)
    if backend is None or not capabilities.per_key:
        return reference_effect_geometry(backend_name=backend_name)

    dimensions_fn = getattr(backend, "dimensions", None)
    if not callable(dimensions_fn):
        return reference_effect_geometry(backend_name=backend_name)

    try:
        dimensions = dimensions_fn()
    except _BACKEND_DISCOVERY_ERRORS:
        logger.exception("Failed to query backend dimensions from '%s'", backend_name)
        return reference_effect_geometry(backend_name=backend_name)

    return effect_geometry_from_dimensions(
        dimensions,
        backend_name=backend_name,
        per_key=True,
    )


def _thread_generation_or_default(engine: _EngineCore, *, default: int) -> int:
    try:
        return int(engine._thread_generation)
    except AttributeError:
        return default


def _query_backend_mapping(
    backend: object | None,
    query_fn: Callable[[], object] | None,
    *,
    mapping_name: str,
) -> dict[str, _BackendDiscoveryValue]:
    if not callable(query_fn):
        return {}
    try:
        raw_mapping = query_fn()
    except _BACKEND_DISCOVERY_ERRORS:  # @quality-exception exception-transparency: backend effect/color discovery is a runtime plugin boundary and engine behavior must degrade to empty backend metadata
        logger.exception("Failed to query backend %s from '%s'", mapping_name, _backend_name(backend))
        return {}
    if not isinstance(raw_mapping, dict):
        return {}
    return dict(raw_mapping or {})


class _EngineCore:
    """Core engine lifecycle and device acquisition."""

    def __init__(self, *, backend: _EffectsBackendProtocol | None = None) -> None:
        self.backend = backend
        self._backend_capabilities_changed: Callable[[BackendCapabilities], None] | None = None
        self._permission_error_cb: Callable[[Exception], None] | None = None
        self.backend_caps = _backend_capabilities(backend)
        self.effect_geometry = _backend_effect_geometry(backend, capabilities=self.backend_caps)
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
        self.reactive_trail_percent = 40
        self.reactive_visual_mode = "subtle"
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
        self._device_mode_off: bool = False
        self._last_reactive_per_key_frame_signature: object | None = None
        self._reactive_state = ReactiveRenderState()

        self._brightness_fade_token: int = 0
        self._brightness_fade_lock = RLock()

    def _ensure_device_available(self) -> bool:
        """Best-effort attempt to connect to the keyboard device."""

        self._refresh_backend_capabilities()
        if self.device_available and not isinstance(self.kb, NullKeyboard):
            return True

        kb, available = acquire_keyboard(kb_lock=self.kb_lock, logger=logger, backend=self.backend)
        self.kb = kb
        self.device_available = bool(available)
        return self.device_available

    def set_backend(self, backend: _EffectsBackendProtocol | None) -> None:
        """Update the selected backend and force the next reacquire through it."""

        self.backend = backend
        self._refresh_backend_capabilities()
        self.mark_device_unavailable()

    def set_backend_capabilities_changed_callback(
        self,
        callback: Callable[[BackendCapabilities], None] | None,
    ) -> None:
        """Publish capability refreshes to the tray's long-lived gating snapshot."""

        self._backend_capabilities_changed = callback
        if callback is not None:
            callback(self.backend_caps)

    def _refresh_backend_capabilities(self) -> None:
        self.backend_caps = _backend_capabilities(self.backend)
        self.effect_geometry = _backend_effect_geometry(self.backend, capabilities=self.backend_caps)
        callback = self._backend_capabilities_changed
        if callback is None:
            return
        try:
            callback(self.backend_caps)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            logger.exception("Failed to publish refreshed backend capabilities")

    def get_backend_effects(self) -> dict[str, HardwareEffectBuilder]:
        if not self.backend_caps.hardware_effects:
            return {}
        backend = self.backend
        return _query_backend_mapping(
            backend,
            _backend_effects_method_or_none(backend),
            mapping_name="effects",
        )

    def get_backend_colors(self) -> dict[str, object]:
        if not self.backend_caps.hardware_effects:
            return {}
        backend = self.backend
        return _query_backend_mapping(
            backend,
            _backend_colors_method_or_none(backend),
            mapping_name="colors",
        )

    def mark_device_unavailable(self) -> None:
        """Force the engine into a safe 'no device' mode."""

        self.device_available = False
        with self.kb_lock:
            old_kb = self.kb
            self.kb = NullKeyboard()

        # Best-effort close of the old device.
        self._last_reactive_per_key_frame_signature = None
        close_fn = getattr(old_kb, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except (AttributeError, OSError, RuntimeError, ValueError):
                logger.debug("Error closing keyboard device on mark_device_unavailable", exc_info=True)

    def close(self) -> None:
        """Stop the current effect and release the keyboard device."""

        self.stop()
        thread = self.thread
        if thread is not None and thread.is_alive():
            logger.warning("Deferring keyboard close while effect thread is still stopping")
            return

        with self.kb_lock:
            old_kb = self.kb
            self.kb = NullKeyboard()

        self.device_available = False

        close_fn = getattr(old_kb, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except (AttributeError, OSError, RuntimeError, ValueError):
                logger.debug("Error closing keyboard device on engine close", exc_info=True)

    def stop(self) -> None:
        """Stop current effect."""

        try:
            self._thread_generation = _thread_generation_or_default(self, default=0) + 1
        except (TypeError, ValueError, OverflowError):
            self._thread_generation = 1

        self._last_rendered_brightness = None
        self._last_hw_mode_brightness = None
        self._last_reactive_per_key_frame_signature = None
        self._reactive_state = ReactiveRenderState()
        # Idle-restore may queue damp timers before start_effect(); stop() would
        # otherwise wipe them and race the first render frames after long idle.
        apply_queued_reactive_restore_seed(self)

        if not self.running and not self.thread:
            self.current_effect = None
            self.stop_event.clear()
            return

        self.running = False
        self.stop_event.set()

        thread = self.thread
        self.current_effect = None

        if thread:
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning("Effect thread did not stop within timeout")
                # Keep both the worker reference and its cancellation event
                # published. Clearing either would allow this blocked worker
                # to resume beside a replacement when hardware I/O unblocks.
                return

        if self.thread is thread:
            self.thread = None
        self.stop_event.clear()
