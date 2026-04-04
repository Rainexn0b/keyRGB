from __future__ import annotations

import logging
from collections.abc import Callable
from threading import RLock, Thread
from typing import Final, Literal, Protocol

from src.core.utils import exceptions as core_exceptions

from .. import catalog as effects_catalog
from .. import hw_payloads as effects_hw_payloads
from ..device import Color, KeyboardDeviceProtocol, PerKeyColorMap
from . import methods as engine_methods

_SW_EFFECTS = effects_catalog.SW_EFFECTS
is_forced_hardware_effect = effects_catalog.is_forced_hardware_effect
normalize_effect_name = effects_catalog.normalize_effect_name
strip_effect_namespace = effects_catalog.strip_effect_namespace
build_hw_effect_payload = effects_hw_payloads.build_hw_effect_payload
_clamped_interval_method = engine_methods.clamped_interval_method
_effect_chase_method = engine_methods.effect_chase_method
_effect_color_cycle_method = engine_methods.effect_color_cycle_method
_effect_rainbow_swirl_method = engine_methods.effect_rainbow_swirl_method
_effect_rainbow_wave_method = engine_methods.effect_rainbow_wave_method
_effect_reactive_fade_method = engine_methods.effect_reactive_fade_method
_effect_reactive_ripple_method = engine_methods.effect_reactive_ripple_method
_effect_spectrum_cycle_method = engine_methods.effect_spectrum_cycle_method
_effect_strobe_method = engine_methods.effect_strobe_method
_effect_twinkle_method = engine_methods.effect_twinkle_method
_fade_in_per_key_method = engine_methods.fade_in_per_key_method
_fade_uniform_color_method = engine_methods.fade_uniform_color_method
_get_interval_method = engine_methods.get_interval_method

logger = logging.getLogger("src.core.effects.engine_start")

_INT_COERCION_ERRORS: Final[tuple[type[BaseException], ...]] = (TypeError, ValueError, OverflowError)
HardwareEffectBuilder = Callable[..., object]


class _ThreadOwner(Protocol):
    thread: Thread | None


class _ManagedEffectThread(Thread):
    """Thread wrapper that clears the published engine thread after join."""

    def __init__(self, *, engine: _ThreadOwner, target: Callable[[], None]) -> None:
        super().__init__(target=target, daemon=True)
        self._engine = engine

    def join(self, timeout: float | None = None) -> None:
        super().join(timeout=timeout)
        if self.is_alive():
            return
        try:
            if getattr(self._engine, "thread", None) is self:
                setattr(self._engine, "thread", None)
        except Exception:  # @quality-exception exception-transparency: engine thread join cleanup is a best-effort boundary; partial engine state must not re-raise from join
            return


class _EngineStart:
    """Effect selection and start/stop orchestration."""

    kb_lock: RLock
    kb: KeyboardDeviceProtocol
    running: bool
    thread: Thread | None
    speed: int
    brightness: int
    current_color: Color
    current_effect: str | None
    per_key_colors: PerKeyColorMap | None
    reactive_color: Color | None
    reactive_use_manual_color: bool
    direction: str | None
    _last_hw_mode_brightness: int | None
    _last_rendered_brightness: int | None
    _thread_generation: int
    stop: Callable[[], None]
    _ensure_device_available: Callable[[], bool]

    _permission_error_cb: Callable[[Exception], None] | None
    get_backend_effects: Callable[[], dict[str, HardwareEffectBuilder]]
    get_backend_colors: Callable[[], dict[str, object]]

    SW_EFFECTS = _SW_EFFECTS

    _SW_START_SPECS: Final[dict[str, tuple[str, Literal["current"] | Color]]] = {
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

    def start_effect(
        self,
        effect_name: str,
        speed: int = 5,
        brightness: int = 25,
        color: Color | None = None,
        reactive_color: Color | None = None,
        reactive_use_manual_color: bool | None = None,
        direction: str | None = None,
    ):
        """Start an effect (hardware or software)."""

        prev_color = tuple(self.current_color)
        prev_effect_was_sw = self.current_effect in self.SW_EFFECTS

        self.stop()
        self._ensure_device_available()

        requested_effect_name = normalize_effect_name(effect_name)
        force_hardware = is_forced_hardware_effect(requested_effect_name)
        effect_name = strip_effect_namespace(requested_effect_name)
        backend_effects = self.get_backend_effects()
        available_hw_effects = frozenset(str(name or "").strip().lower() for name in backend_effects.keys())
        known_effects = frozenset(self.SW_EFFECTS) | available_hw_effects

        if effect_name not in known_effects:
            raise ValueError(f"Unknown effect: {effect_name}. Valid: {', '.join(sorted(known_effects))}")

        self.current_effect = effect_name
        self.speed = max(0, min(10, speed))
        self.brightness = max(0, min(50, brightness))

        if color:
            self.current_color = color

        if reactive_color is not None:
            self.reactive_color = reactive_color

        if reactive_use_manual_color is not None:
            self.reactive_use_manual_color = bool(reactive_use_manual_color)

        if direction is not None:
            self.direction = direction

        is_backend_hw_effect = effect_name in available_hw_effects

        if force_hardware or (is_backend_hw_effect and effect_name not in self.SW_EFFECTS):
            self._start_hw_effect(effect_name)
        else:
            spec = self._SW_START_SPECS.get(effect_name)
            if spec is None:
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
                from_sw_effect=prev_effect_was_sw,
            )

    def _start_sw_effect(
        self,
        *,
        target: Callable[[], None],
        prev_color: Color,
        fade_to_color: Color,
        from_sw_effect: bool = False,
    ) -> None:
        if from_sw_effect:
            pass
        elif int(self.brightness) > 1:
            if self.per_key_colors and hasattr(self.kb, "set_key_colors"):
                self._fade_in_per_key(duration_s=0.06)
                self._last_hw_mode_brightness = int(self.brightness)
                self._last_rendered_brightness = int(self.brightness)
            else:
                self._fade_uniform_color(
                    from_color=prev_color,
                    to_color=fade_to_color,
                    brightness=int(self.brightness),
                    duration_s=0.06,
                )
                self._last_rendered_brightness = int(self.brightness)
        elif self.per_key_colors and hasattr(self.kb, "set_key_colors"):
            from src.core.effects.perkey_animation import enable_user_mode_once

            enable_user_mode_once(kb=self.kb, kb_lock=self.kb_lock, brightness=0)
            self._last_hw_mode_brightness = 0

        try:
            self._thread_generation = int(getattr(self, "_thread_generation", 0)) + 1
        except _INT_COERCION_ERRORS:
            self._thread_generation = 1
        run_generation = int(getattr(self, "_thread_generation", 1))

        def _run_target_best_effort() -> None:
            try:
                target()
            except Exception as exc:  # @quality-exception exception-transparency: effect thread top-level boundary; dispatches permission/disconnect classification before logging unhandled errors
                if core_exceptions.is_permission_denied(exc):
                    callback = getattr(self, "_permission_error_cb", None)
                    if callable(callback):
                        try:
                            callback(exc)
                        except Exception:  # @quality-exception exception-transparency: permission error callback is a user-injected boundary and must not break the permission-error handling path
                            logger.exception("Permission error callback failed")
                    logger.warning(
                        "Permission denied while applying effect: %s",
                        exc,
                        exc_info=True,
                    )
                    return

                if core_exceptions.is_device_disconnected(exc):
                    try:
                        mark = getattr(self, "mark_device_unavailable", None)
                        if callable(mark):
                            mark()
                    except Exception:  # @quality-exception exception-transparency: mark_device_unavailable is a hardware-state bookkeeping boundary and failures must not interrupt the disconnect-handling path
                        logger.exception("Failed to mark keyboard device unavailable after disconnect")
                    logger.warning(
                        "Keyboard device disconnected while applying effect: %s",
                        exc,
                        exc_info=True,
                    )
                    return

                logger.exception("Unhandled exception in effect thread")
            finally:
                stale_generation = False
                try:
                    stale_generation = int(getattr(self, "_thread_generation", 0)) != run_generation
                except _INT_COERCION_ERRORS:
                    stale_generation = False

                if not stale_generation:
                    self.running = False

        self.running = True
        thread_ref = _ManagedEffectThread(engine=self, target=_run_target_best_effort)
        self.thread = thread_ref
        thread_ref.start()

    def _start_hw_effect(self, effect_name: str) -> None:
        """Start hardware effect."""

        backend_effects = self.get_backend_effects()
        effect_func = backend_effects.get(effect_name)
        if not effect_func:
            logger.warning("Hardware effect not supported by backend: %s", effect_name)
            with self.kb_lock:
                self.kb.set_color(tuple(self.current_color), brightness=int(self.brightness))
            return

        backend_colors = self.get_backend_colors()
        effect_data = build_hw_effect_payload(
            effect_name=effect_name,
            effect_func=effect_func,
            ui_speed=int(self.speed),
            brightness=int(self.brightness),
            current_color=tuple(self.current_color),
            hw_colors=backend_colors,
            kb=self.kb,
            kb_lock=self.kb_lock,
            logger=logger,
            direction=getattr(self, "direction", None),
        )

        with self.kb_lock:
            self.kb.set_effect(effect_data)

    _get_interval = _get_interval_method
    _clamped_interval = _clamped_interval_method
    _fade_uniform_color = _fade_uniform_color_method
    _fade_in_per_key = _fade_in_per_key_method
    _effect_rainbow_wave = _effect_rainbow_wave_method
    _effect_rainbow_swirl = _effect_rainbow_swirl_method
    _effect_spectrum_cycle = _effect_spectrum_cycle_method
    _effect_color_cycle = _effect_color_cycle_method
    _effect_chase = _effect_chase_method
    _effect_twinkle = _effect_twinkle_method
    _effect_strobe = _effect_strobe_method
    _effect_reactive_fade = _effect_reactive_fade_method
    _effect_reactive_ripple = _effect_reactive_ripple_method
