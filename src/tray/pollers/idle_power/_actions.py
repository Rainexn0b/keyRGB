from __future__ import annotations

import time
from collections.abc import Callable
from typing import Optional, cast

from src.core.utils.safe_attrs import safe_int_attr
from src.tray.controllers._transition_constants import (
    SOFT_OFF_FADE_DURATION_S,
    SOFT_ON_FADE_DURATION_S,
    SOFT_ON_START_BRIGHTNESS,
)
from src.tray.protocols import IdlePowerTrayProtocol, LightingTrayProtocol


def _set_engine_hw_brightness_cap(engine: object, brightness: int | None) -> None:
    """Set/clear the reactive render brightness cap on the engine.

    Used by temp-dim flows so reactive effects do not raise hardware
    brightness above a temporary policy target. Also propagates the
    ``_dim_temp_active`` flag so ``_resolve_brightness()`` can lock HW
    brightness to the dim target.
    """

    try:
        if brightness is None:
            engine._hw_brightness_cap = None  # type: ignore[attr-defined]
            engine._dim_temp_active = False  # type: ignore[attr-defined]
            return

        engine._hw_brightness_cap = max(0, min(50, int(brightness)))  # type: ignore[attr-defined]
        engine._dim_temp_active = True  # type: ignore[attr-defined]
    except Exception:
        return


def _set_reactive_transition(
    engine: object,
    *,
    target_brightness: int,
    duration_s: float,
) -> None:
    """Seed a render-time reactive brightness transition."""

    try:
        current_i = safe_int_attr(
            engine,
            "_last_rendered_brightness",
            default=safe_int_attr(engine, "brightness", default=target_brightness),
            min_v=0,
            max_v=50,
        )
        target_i = max(0, min(50, int(target_brightness)))
        engine._reactive_transition_from_brightness = current_i  # type: ignore[attr-defined]
        engine._reactive_transition_to_brightness = target_i  # type: ignore[attr-defined]
        engine._reactive_transition_started_at = float(time.monotonic())  # type: ignore[attr-defined]
        engine._reactive_transition_duration_s = max(0.0, float(duration_s))  # type: ignore[attr-defined]
    except Exception:
        return


def _set_brightness_best_effort(
    engine: object,
    brightness: int,
    *,
    apply_to_hardware: bool,
    fade: bool,
    fade_duration_s: float,
) -> None:
    """Call engine.set_brightness with compatibility fallbacks."""

    try:
        set_brightness = getattr(engine, "set_brightness", None)
        if not callable(set_brightness):
            return
        set_brightness_fn = cast(Callable[..., object], set_brightness)

        set_brightness_fn(
            int(brightness),
            apply_to_hardware=bool(apply_to_hardware),
            fade=bool(fade),
            fade_duration_s=float(fade_duration_s),
        )
        return
    except TypeError:
        try:
            set_brightness_fn(int(brightness), apply_to_hardware=bool(apply_to_hardware))
        except Exception:
            pass
    except Exception:
        pass


def restore_from_idle(tray: IdlePowerTrayProtocol) -> None:
    tray.is_off = False
    tray._idle_forced_off = False
    try:
        if hasattr(tray, "engine"):
            _set_engine_hw_brightness_cap(tray.engine, None)
    except Exception:
        pass

    try:
        if hasattr(tray, "engine"):
            tray.engine.current_color = (0, 0, 0)
    except Exception:
        pass

    try:
        if safe_int_attr(tray.config, "brightness", default=0) == 0:
            tray.config.brightness = safe_int_attr(tray, "_last_brightness", default=25)
    except Exception:
        pass

    try:
        start_fn = getattr(tray, "_start_current_effect", None)
        if callable(start_fn):
            try:
                start_fn(
                    brightness_override=SOFT_ON_START_BRIGHTNESS,
                    fade_in=True,
                    fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
                )
            except TypeError:
                start_fn()
        else:
            from src.tray.controllers.lighting_controller import start_current_effect

            start_current_effect(
                cast(LightingTrayProtocol, tray),
                brightness_override=SOFT_ON_START_BRIGHTNESS,
                fade_in=True,
                fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
            )
    except Exception:
        try:
            tray._log_exception("Failed to restore lighting after idle", Exception("restore failed"))
        except Exception:
            pass

    try:
        refresh_fn = getattr(tray, "_refresh_ui", None)
        if callable(refresh_fn):
            refresh_fn()
    except Exception:
        pass


def apply_idle_action(
    tray: IdlePowerTrayProtocol,
    *,
    action: Optional[str],
    dim_temp_brightness: int,
    restore_from_idle_fn: Callable[[IdlePowerTrayProtocol], None],
    reactive_effects_set: frozenset[str],
    sw_effects_set: frozenset[str],
) -> None:
    if action == "turn_off":
        tray._dim_temp_active = False
        tray._dim_temp_target_brightness = None
        try:
            _set_engine_hw_brightness_cap(tray.engine, None)
        except Exception:
            pass
        try:
            tray.engine.stop()
        except Exception:
            pass
        try:
            tray.engine.turn_off(fade=True, fade_duration_s=SOFT_OFF_FADE_DURATION_S)
        except Exception:
            pass

        tray.is_off = True
        tray._idle_forced_off = True
        try:
            refresh_fn = getattr(tray, "_refresh_ui", None)
            if callable(refresh_fn):
                refresh_fn()
        except Exception:
            pass
        return

    if action == "dim_to_temp":
        if not bool(getattr(tray, "is_off", False)):
            try:
                if bool(getattr(tray, "_dim_temp_active", False)) and int(
                    getattr(tray, "_dim_temp_target_brightness", -1) or -1
                ) == int(dim_temp_brightness):
                    return
            except Exception:
                pass
            tray._dim_temp_active = True
            tray._dim_temp_target_brightness = int(dim_temp_brightness)
            try:
                effect = str(getattr(getattr(tray, "config", None), "effect", "none") or "none")
            except Exception:
                effect = "none"
            try:
                is_sw_effect = effect in sw_effects_set
                if effect in reactive_effects_set:
                    with tray.engine.kb_lock:
                        tray.engine._dim_temp_active = True  # type: ignore[attr-defined]
                        _set_reactive_transition(
                            tray.engine,
                            target_brightness=int(dim_temp_brightness),
                            duration_s=SOFT_OFF_FADE_DURATION_S,
                        )
                        tray.engine.per_key_brightness = dim_temp_brightness
                        _set_brightness_best_effort(
                            tray.engine,
                            dim_temp_brightness,
                            apply_to_hardware=False,
                            fade=False,
                            fade_duration_s=0.0,
                        )
                else:
                    _set_brightness_best_effort(
                        tray.engine,
                        dim_temp_brightness,
                        apply_to_hardware=not is_sw_effect,
                        fade=True,
                        fade_duration_s=0.25,
                    )
            except Exception:
                pass
        return

    if action == "restore_brightness":
        tray._dim_temp_active = False
        tray._dim_temp_target_brightness = None
        try:
            target = safe_int_attr(tray.config, "brightness", default=0)
            perkey_target = safe_int_attr(tray.config, "perkey_brightness", default=0)
            effect = str(getattr(getattr(tray, "config", None), "effect", "none") or "none")
        except Exception:
            target = 0
            perkey_target = 0
            effect = "none"
        if target > 0 and not bool(getattr(tray, "is_off", False)):
            try:
                is_sw_effect = effect in sw_effects_set
                if effect in reactive_effects_set:
                    restore_target_hw = max(int(target), int(perkey_target))
                    with tray.engine.kb_lock:
                        _set_reactive_transition(
                            tray.engine,
                            target_brightness=restore_target_hw,
                            duration_s=SOFT_ON_FADE_DURATION_S,
                        )
                        _set_engine_hw_brightness_cap(tray.engine, None)
                        tray.engine.per_key_brightness = perkey_target
                        _set_brightness_best_effort(
                            tray.engine,
                            target,
                            apply_to_hardware=False,
                            fade=False,
                            fade_duration_s=0.0,
                        )
                else:
                    _set_brightness_best_effort(
                        tray.engine,
                        target,
                        apply_to_hardware=not is_sw_effect,
                        fade=True,
                        fade_duration_s=0.25,
                    )
            except Exception:
                pass
        return

    if action == "restore":
        if not bool(getattr(tray, "_user_forced_off", False)) and not bool(getattr(tray, "_power_forced_off", False)):
            tray._dim_temp_active = False
            tray._dim_temp_target_brightness = None
            try:
                _set_engine_hw_brightness_cap(tray.engine, None)
            except Exception:
                pass
            restore_from_idle_fn(tray)
        return
