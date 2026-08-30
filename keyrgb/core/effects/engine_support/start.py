from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from threading import Lock, RLock, Thread
from typing import Final, cast

from keyrgb.core.backends.base import BackendCapabilities
from keyrgb.core.effects.effect_contract import CURRENT_COLOR
from keyrgb.core.effects.registry import get_effect_registration
from keyrgb.core.utils import exceptions as core_exceptions

from .. import catalog as effects_catalog, hw_payloads as effects_hw_payloads
from ..device import Color, KeyboardDeviceProtocol, PerKeyColorMap
from . import _start_support, methods as engine_methods

_SW_EFFECTS = effects_catalog.SW_EFFECTS
is_forced_hardware_effect = effects_catalog.is_forced_hardware_effect
normalize_effect_name = effects_catalog.normalize_effect_name
strip_effect_namespace = effects_catalog.strip_effect_namespace
build_hw_effect_payload = effects_hw_payloads.build_hw_effect_payload
_ManagedEffectThread = _start_support._ManagedEffectThread
_mark_device_unavailable_best_effort = _start_support._mark_device_unavailable_best_effort
_notify_permission_error_callback_best_effort = _start_support._notify_permission_error_callback_best_effort
_thread_generation_or_default = _start_support._thread_generation_or_default
_clamped_interval_method = engine_methods.clamped_interval_method
_fade_in_per_key_method = engine_methods.fade_in_per_key_method
_fade_uniform_color_method = engine_methods.fade_uniform_color_method
_get_interval_method = engine_methods.get_interval_method
_prime_per_key_frame_method = engine_methods.prime_per_key_frame_method

logger = logging.getLogger("keyrgb.core.effects.engine_start")

_INT_COERCION_ERRORS: Final[tuple[type[Exception], ...]] = (TypeError, ValueError, OverflowError)
_EFFECT_THREAD_RUNTIME_ERRORS: Final[tuple[type[Exception], ...]] = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
HardwareEffectBuilder = Callable[..., object]


class _EngineStart:
    """Effect selection and start/stop orchestration."""

    kb_lock: RLock
    _start_lock: Lock
    kb: KeyboardDeviceProtocol
    backend_caps: BackendCapabilities
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
    _device_mode_off: bool
    _last_rendered_brightness: int | None
    _thread_generation: int
    stop: Callable[[], None]
    _ensure_device_available: Callable[[], bool]
    _invalidate_brightness_fade: Callable[[], int]

    _permission_error_cb: Callable[[Exception], None] | None
    get_backend_effects: Callable[[], dict[str, HardwareEffectBuilder]]
    get_backend_colors: Callable[[], dict[str, object]]

    SW_EFFECTS = _SW_EFFECTS

    def start_effect(
        self,
        effect_name: str,
        speed: int = 5,
        brightness: int = 25,
        color: Color | None = None,
        reactive_color: Color | None = None,
        reactive_use_manual_color: bool | None = None,
        reactive_visual_mode: str | None = None,
        direction: str | None = None,
        *,
        preserve_last_rendered_brightness: bool = False,
    ):
        """Start an effect (hardware or software)."""

        # The whole stop/configure/publish region runs under the dedicated
        # lifecycle lock (KSW-5). Two concurrent direct starts would otherwise
        # interleave: both could clear the previous worker and publish their own
        # software worker, orphaning the first as a second live deck writer that
        # keeps repainting forever. Holding _start_lock here makes the region
        # atomic — only one start at a time can reach the publish step, and it
        # always stops the previously published worker first. _start_lock is the
        # outermost engine lock (kb_lock/_brightness_fade_lock are taken only
        # inside it). It remains held across stop()'s worker join by design, but
        # kb_lock is not held there, so the worker can finish any final output.
        with self._start_lock:
            # A brightness fade (screen-dim/idle turn_off, power brightness change)
            # can still be stepping on another thread. Advance the fade token before
            # any write this start performs, so the superseded operation commits no
            # later brightness step, off, or target write over the replacement
            # effect. The replacement's own fades (_fade_uniform_color /
            # _fade_in_per_key) do not consult the token, so they stay intact.
            self._invalidate_brightness_fade()

            prev_color = self.current_color
            prev_effect_was_sw = self.current_effect in self.SW_EFFECTS
            preserved_last_rendered = self._last_rendered_brightness if preserve_last_rendered_brightness else None

            self.stop()
            previous_thread = self.thread
            if previous_thread is not None and previous_thread.is_alive():
                raise RuntimeError("Previous effect thread is still stopping; replacement effect was not started")
            if preserved_last_rendered is not None:
                # Config-apply restarts happen while the keyboard is already lit.
                # Restore this baseline before the replacement render thread is
                # created so its first frame cannot observe the stop() sentinel.
                self._last_rendered_brightness = preserved_last_rendered
            self._ensure_device_available()

            requested_effect_name = normalize_effect_name(effect_name)
            force_hardware = is_forced_hardware_effect(requested_effect_name)
            effect_name = strip_effect_namespace(requested_effect_name)
            backend_effects = self.get_backend_effects()
            available_hw_effects = frozenset(str(name or "").strip().lower() for name in backend_effects)
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

            if reactive_visual_mode is not None:
                normalized_visual_mode = str(reactive_visual_mode or "subtle").strip().lower()
                self.reactive_visual_mode = (
                    normalized_visual_mode if normalized_visual_mode in {"subtle", "vivid"} else "subtle"
                )

            if direction is not None:
                self.direction = direction

            is_backend_hw_effect = effect_name in available_hw_effects

            if force_hardware or (is_backend_hw_effect and effect_name not in self.SW_EFFECTS):
                self._start_hw_effect(effect_name)
            else:
                registration = get_effect_registration(effect_name)
                if registration is None:
                    raise ValueError(f"Unhandled effect: {effect_name}")

                if registration.start_color == CURRENT_COLOR:
                    fade_to_color = self.current_color
                else:
                    fade_to_color = registration.start_color

                self._start_sw_effect(
                    target=partial(registration.runner, self),
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
        start_brightness = int(self.brightness)
        # Soft-on idle/menu/controller-sleep restore starts at
        # SOFT_ON_START_BRIGHTNESS (1). Two failure modes left ITE boards dark:
        # 1) brightness==1 skipped the per-key prime and only called
        #    enable_user_mode(0) after an explicit turn_off;
        # 2) firmware controller-sleep reports brightness=0 with is_off=False,
        #    so _device_mode_off stayed False and restore faded with
        #    enable_user_mode=False — journaled stuck-dark after
        #    controller_sleep_restore.
        device_mode_off = bool(self._device_mode_off)
        soft_on_start = start_brightness == 1
        # Reassert user mode after explicit turn_off *or* soft-on from a dark
        # deck (idle restore / menu turn-on / controller-sleep restore).
        needs_mode_reassert = start_brightness >= 1 and (device_mode_off or soft_on_start)
        needs_perkey_prime = (
            bool(self.per_key_colors)
            and self.backend_caps.per_key
            and callable(getattr(self.kb, "set_key_colors", None))
            and (start_brightness > 1 or needs_mode_reassert)
        )

        if from_sw_effect:
            pass
        elif needs_perkey_prime:
            if self._prime_per_key_frame():
                self._last_hw_mode_brightness = start_brightness
                self._last_rendered_brightness = start_brightness
            else:
                self._fade_in_per_key(duration_s=0.06)
                self._last_hw_mode_brightness = start_brightness
                self._last_rendered_brightness = start_brightness
            # Prime (with reassert) and the fade-in fallback both send a
            # mode command when the device was explicitly turned off.
            self._device_mode_off = False
        elif start_brightness > 1 or needs_mode_reassert:
            self._fade_uniform_color(
                from_color=prev_color,
                to_color=fade_to_color,
                brightness=start_brightness,
                duration_s=0.06,
            )
            self._last_rendered_brightness = start_brightness
            # set_color re-enables user mode on the controller.
            self._device_mode_off = False
        elif self.per_key_colors and self.backend_caps.per_key and callable(getattr(self.kb, "set_key_colors", None)):
            from keyrgb.core.effects.perkey_animation import enable_user_mode_once

            # Never arm user mode at brightness 0 after a dark deck — ITE
            # stays unlit; use at least soft-on level 1.
            enable_user_mode_once(kb=self.kb, kb_lock=self.kb_lock, brightness=max(1, start_brightness))
            self._last_hw_mode_brightness = max(1, start_brightness)
            self._device_mode_off = False

        try:
            self._thread_generation = _thread_generation_or_default(self, default=0) + 1
        except _INT_COERCION_ERRORS:
            self._thread_generation = 1
        run_generation = _thread_generation_or_default(self, default=1)

        def _run_target_best_effort() -> None:
            try:
                target()
            except _EFFECT_THREAD_RUNTIME_ERRORS as exc:
                if core_exceptions.is_permission_denied(exc):
                    _notify_permission_error_callback_best_effort(self, exc)
                    logger.warning(
                        "Permission denied while applying effect: %s",
                        exc,
                        exc_info=True,
                    )
                    return

                if core_exceptions.is_device_disconnected(exc):
                    _mark_device_unavailable_best_effort(self)
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
                    stale_generation = _thread_generation_or_default(self, default=0) != run_generation
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
            # set_color re-enables user mode on the controller.
            self._device_mode_off = False
            return

        backend_colors = cast(dict[str, int], self.get_backend_colors())
        effect_data = build_hw_effect_payload(
            effect_name=effect_name,
            effect_func=effect_func,
            ui_speed=int(self.speed),
            brightness=int(self.brightness),
            current_color=self.current_color,
            hw_colors=backend_colors,
            kb=self.kb,
            kb_lock=self.kb_lock,
            logger=logger,
            direction=self.direction,
        )

        with self.kb_lock:
            self.kb.set_effect(effect_data)
        # Programming a hardware effect takes the controller out of its
        # explicit off mode.
        self._device_mode_off = False

    _get_interval = _get_interval_method
    _clamped_interval = _clamped_interval_method
    _fade_uniform_color = _fade_uniform_color_method
    _fade_in_per_key = _fade_in_per_key_method
    _prime_per_key_frame = _prime_per_key_frame_method
