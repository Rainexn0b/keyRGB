from __future__ import annotations

import logging
from threading import Thread
from typing import Any, Final, Literal, Optional, Tuple, cast

from src.core.effects.catalog import (
    ALL_EFFECTS as _ALL_EFFECTS,
    HW_EFFECTS as _HW_EFFECTS,
    SW_EFFECTS as _SW_EFFECTS,
    normalize_effect_name,
)
from src.core.effects.fades import fade_in_per_key, fade_uniform_color
from src.core.effects.hw_payloads import build_hw_effect_payload
from src.core.effects.ite_backend import hw_colors, hw_effects
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
    per_key_colors: Any
    reactive_color: Optional[tuple]
    reactive_use_manual_color: bool
    stop: Any
    _ensure_device_available: Any

    # Optional callback invoked when hardware I/O fails due to permissions.
    # Signature: cb(exc: Exception) -> None
    _permission_error_cb: Any

    HW_EFFECTS = _HW_EFFECTS
    SW_EFFECTS = _SW_EFFECTS
    ALL_EFFECTS = _ALL_EFFECTS

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
    ):
        """Start an effect (hardware or software)."""

        prev_color = tuple(self.current_color)

        self.stop()

        # If no device is present, keep state but do not crash.
        self._ensure_device_available()

        effect_name = normalize_effect_name(effect_name)

        if effect_name not in self.ALL_EFFECTS:
            raise ValueError(f"Unknown effect: {effect_name}. Valid: {', '.join(self.ALL_EFFECTS)}")

        # If a backend doesn't expose hardware effects (e.g. sysfs-leds),
        # some catalog entries like 'rainbow' may not be supported. Provide
        # a best-effort fallback instead of raising and spamming tracebacks.
        if effect_name in self.HW_EFFECTS and effect_name not in hw_effects:
            if effect_name == "rainbow":
                effect_name = "rainbow_wave"
            else:
                effect_name = "none"

        self.current_effect = effect_name
        self.speed = max(0, min(10, speed))
        self.brightness = max(0, min(50, brightness))

        if color:
            self.current_color = color

        if reactive_color is not None:
            self.reactive_color = reactive_color

        if reactive_use_manual_color is not None:
            self.reactive_use_manual_color = bool(reactive_use_manual_color)

        # Hardware effects - delegate to controller
        if effect_name in self.HW_EFFECTS:
            self._start_hw_effect(effect_name)

        # Software effects - run in a worker thread
        else:
            spec = self._SW_START_SPECS.get(effect_name)
            if spec is None:
                # Should not happen due to earlier validation against ALL_EFFECTS.
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
            )

    def _start_sw_effect(
        self,
        *,
        target,
        prev_color: tuple,
        fade_to_color: tuple,
    ) -> None:
        if self.per_key_colors and hasattr(self.kb, "set_key_colors"):
            self._fade_in_per_key(duration_s=0.06)
        else:
            # Fade from previous color to the chosen effect's start color.
            self._fade_uniform_color(
                from_color=prev_color,
                to_color=fade_to_color,
                brightness=int(self.brightness),
                duration_s=0.06,
            )

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
                            pass
                    try:
                        logger.warning("Permission denied while applying effect: %s", exc)
                    except Exception:
                        pass
                    return

                # If the device vanished, stop issuing I/O until reacquired.
                if is_device_disconnected(exc):
                    try:
                        mark = getattr(self, "mark_device_unavailable", None)
                        if callable(mark):
                            mark()
                    except Exception:
                        pass
                    try:
                        logger.warning("Keyboard device disconnected while applying effect: %s", exc)
                    except Exception:
                        pass
                    return

                logger.exception("Unhandled exception in effect thread")
            finally:
                # If the thread exits (error or normal), keep state consistent.
                try:
                    self.running = False
                except Exception:
                    pass

        self.running = True
        self.thread = Thread(target=_run_target_best_effort, daemon=True)
        self.thread.start()

    def _start_hw_effect(self, effect_name: str):
        """Start hardware effect."""

        effect_func = hw_effects.get(effect_name)
        if not effect_func:
            # Backend doesn't expose this effect; fall back to a static color.
            try:
                logger.warning("Hardware effect not supported by backend: %s", effect_name)
            except Exception:
                pass
            with self.kb_lock:
                self.kb.set_color(tuple(self.current_color), brightness=int(self.brightness))
            return

        effect_data = build_hw_effect_payload(
            effect_name=effect_name,
            effect_func=effect_func,
            ui_speed=int(self.speed),
            brightness=int(self.brightness),
            current_color=tuple(self.current_color),
            hw_colors=hw_colors,
            kb=self.kb,
            kb_lock=self.kb_lock,
            logger=logger,
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
