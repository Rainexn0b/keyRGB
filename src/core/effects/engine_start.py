from __future__ import annotations

import logging
from collections.abc import Mapping
from threading import Thread
from typing import Any, Final, Literal, Optional, Tuple, cast

from src.core.effects.catalog import (
    SW_EFFECTS as _SW_EFFECTS,
    is_forced_hardware_effect,
    normalize_effect_name,
    strip_effect_namespace,
)
from src.core.effects.fades import fade_in_per_key, fade_uniform_color
from src.core.effects.hw_payloads import build_hw_effect_payload
from src.core.effects.software.effects import (
    run_chase,
    run_color_cycle,
    run_rainbow_swirl,
    run_rainbow_wave,
    run_spectrum_cycle,
    run_strobe,
    run_twinkle,
)
from src.core.effects.reactive.effects import (
    run_reactive_fade,
    run_reactive_ripple,
)
from src.core.effects.timing import clamped_interval, get_interval
from src.core.utils.exceptions import is_device_disconnected, is_permission_denied

logger = logging.getLogger(__name__)

_INT_COERCION_ERRORS: Final[tuple[type[BaseException], ...]] = (TypeError, ValueError, OverflowError)


class _EngineStart:
    """Effect selection and start/stop orchestration."""

    # Declared for static type checkers (provided by _EngineCore / composed class).
    kb_lock: Any
    kb: Any
    running: bool
    thread: Any
    speed: int
    brightness: int
    current_color: tuple
    current_effect: Optional[str]
    per_key_colors: Mapping[Any, Any] | None
    reactive_color: Optional[tuple]
    reactive_use_manual_color: bool
    direction: Optional[str]
    _last_hw_mode_brightness: Optional[int]
    _last_rendered_brightness: Optional[int]
    _thread_generation: int
    stop: Any
    _ensure_device_available: Any

    # Optional callback invoked when hardware I/O fails due to permissions.
    # Signature: cb(exc: Exception) -> None
    _permission_error_cb: Any
    get_backend_effects: Any
    get_backend_colors: Any

    SW_EFFECTS = _SW_EFFECTS

    _SW_START_SPECS: Final[dict[str, tuple[str, Literal["current"] | Tuple[int, int, int]]]] = {
        # Effect name -> (method_name, fade_to)
        # fade_to: "current" uses self.current_color; otherwise a literal RGB tuple.
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
        color: Optional[tuple] = None,
        reactive_color: Optional[tuple] = None,
        reactive_use_manual_color: Optional[bool] = None,
        direction: Optional[str] = None,
    ):
        """Start an effect (hardware or software)."""

        prev_color = tuple(self.current_color)
        prev_effect_was_sw = self.current_effect in self.SW_EFFECTS

        self.stop()

        # If no device is present, keep state but do not crash.
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

        # Hardware effects - delegate to controller
        is_backend_hw_effect = effect_name in available_hw_effects

        if force_hardware or (is_backend_hw_effect and effect_name not in self.SW_EFFECTS):
            self._start_hw_effect(effect_name)

        # Software effects - run in a worker thread
        else:
            spec = self._SW_START_SPECS.get(effect_name)
            if spec is None:
                # Should not happen due to earlier validation against the
                # backend-owned hardware set plus canonical software effects.
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
        target,
        prev_color: tuple,
        fade_to_color: tuple,
        from_sw_effect: bool = False,
    ) -> None:
        if from_sw_effect:
            # The keyboard is already in user mode from the previous software
            # effect's last frame.  Starting the fade-in from near-black would
            # create a visible dark dip between effects.  Skip the fade and let
            # the new thread's first frame write directly at full brightness.
            pass
        elif int(self.brightness) > 1:
            if self.per_key_colors and hasattr(self.kb, "set_key_colors"):
                self._fade_in_per_key(duration_s=0.06)
                # Record the mode brightness established by the per-key fade so
                # the reactive render's first frame doesn't send a redundant
                # SET_EFFECT (enable_user_mode).
                self._last_hw_mode_brightness = int(self.brightness)
                # Seed _last_rendered_brightness so the per-frame stability
                # guard treats the fade endpoint as the starting point.
                # Without this, the guard sees prev=None→0 and clamps the
                # first reactive frame down to 8 (0+step), producing a
                # visible dip from the fade's brightness before ramping back.
                self._last_rendered_brightness = int(self.brightness)
            else:
                # Fade from previous color to the chosen effect's start color.
                self._fade_uniform_color(
                    from_color=prev_color,
                    to_color=fade_to_color,
                    brightness=int(self.brightness),
                    duration_s=0.06,
                )
                # Seed _last_rendered_brightness so the per-frame stability
                # guard starts from the fade's final brightness, not from 0.
                # Without this, the guard sees prev=None→0 and steps up
                # frame-by-frame from 0 to engine.brightness, producing a
                # visible sweep-to-brightness at effect start.
                self._last_rendered_brightness = int(self.brightness)
        elif self.per_key_colors and hasattr(self.kb, "set_key_colors"):
            # At very low brightness (e.g. brightness_override=1 during a
            # wake-from-idle restore) the cosmetic fade is invisible.
            # Initialise user mode at brightness=0 so the SET_EFFECT mode-
            # init is invisible.  The render loop then ramps using the
            # lighter SET_BRIGHTNESS command (no mode reinit, no flash).
            from src.core.effects.perkey_animation import enable_user_mode_once

            enable_user_mode_once(kb=self.kb, kb_lock=self.kb_lock, brightness=0)
            self._last_hw_mode_brightness = 0

        try:
            self._thread_generation = int(getattr(self, "_thread_generation", 0)) + 1
        except _INT_COERCION_ERRORS:
            self._thread_generation = 1
        run_generation = int(getattr(self, "_thread_generation", 1))
        thread_ref: Thread | None = None

        def _run_target_best_effort() -> None:
            try:
                target()
            except Exception as exc:
                # Permission failures are common when udev/polkit rules are missing.
                if is_permission_denied(exc):
                    cb = getattr(self, "_permission_error_cb", None)
                    if callable(cb):
                        try:
                            cb(exc)
                        except Exception:
                            logger.exception("Permission error callback failed")
                    logger.warning(
                        "Permission denied while applying effect: %s",
                        exc,
                        exc_info=True,
                    )
                    return

                # If the device vanished, stop issuing I/O until reacquired.
                if is_device_disconnected(exc):
                    try:
                        mark = getattr(self, "mark_device_unavailable", None)
                        if callable(mark):
                            mark()
                    except Exception:
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
                    if thread_ref is not None and getattr(self, "thread", None) is thread_ref:
                        self.thread = None

        self.running = True
        thread_ref = Thread(target=_run_target_best_effort, daemon=True)
        self.thread = thread_ref
        thread_ref.start()

    def _start_hw_effect(self, effect_name: str):
        """Start hardware effect."""

        backend_effects = self.get_backend_effects()
        effect_func = backend_effects.get(effect_name)
        if not effect_func:
            # Backend doesn't expose this effect; fall back to a static color.
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

    # ===== SOFTWARE EFFECTS =====

    def _get_interval(self, base_ms: int) -> float:
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
        fade_in_per_key(
            kb=self.kb,
            kb_lock=self.kb_lock,
            per_key_colors=self.per_key_colors,
            current_color=self.current_color,
            brightness=int(self.brightness),
            duration_s=duration_s,
            steps=steps,
        )

    def _effect_rainbow_wave(self):
        run_rainbow_wave(cast(Any, self))

    def _effect_rainbow_swirl(self):
        run_rainbow_swirl(cast(Any, self))

    def _effect_spectrum_cycle(self):
        run_spectrum_cycle(cast(Any, self))

    def _effect_color_cycle(self):
        run_color_cycle(cast(Any, self))

    def _effect_chase(self):
        run_chase(cast(Any, self))

    def _effect_twinkle(self):
        run_twinkle(cast(Any, self))

    def _effect_strobe(self):
        run_strobe(cast(Any, self))

    def _effect_reactive_fade(self):
        run_reactive_fade(cast(Any, self))

    def _effect_reactive_ripple(self):
        run_reactive_ripple(cast(Any, self))
