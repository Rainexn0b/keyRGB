from __future__ import annotations

from collections.abc import Callable
from typing import Optional, cast

from src.core.utils.safe_attrs import safe_int_attr
from src.tray.protocols import IdlePowerTrayProtocol, LightingTrayProtocol


def _set_brightness_best_effort(
    engine: object,
    brightness: int,
    *,
    apply_to_hardware: bool,
    fade: bool,
    fade_duration_s: float,
) -> None:
    """Call engine.set_brightness with compatibility fallbacks.

    Some unit tests and alternate engine implementations only accept
    (brightness, apply_to_hardware=...) and do not support fade kwargs.
    """

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
        # Retry without fade-related kwargs.
        try:
            set_brightness_fn(int(brightness), apply_to_hardware=bool(apply_to_hardware))
        except Exception:
            pass
    except Exception:
        pass


def restore_from_idle(tray: IdlePowerTrayProtocol) -> None:
    tray.is_off = False
    tray._idle_forced_off = False

    # When restoring from an off state (screen dim sync / DPMS), avoid using a stale
    # previous color as the fade start. Some devices visibly flash if the first
    # restored frame briefly jumps to the last saved color at full brightness.
    try:
        if hasattr(tray, "engine"):
            tray.engine.current_color = (0, 0, 0)
    except Exception:
        pass

    # Best-effort: if brightness is 0, fall back to last brightness.
    try:
        if safe_int_attr(tray.config, "brightness", default=0) == 0:
            tray.config.brightness = safe_int_attr(tray, "_last_brightness", default=25)
    except Exception:
        pass

    try:
        # Use a fade-in when restoring from an off/idle state to avoid abrupt
        # jumps on some firmware/backends.
        start_fn = getattr(tray, "_start_current_effect", None)
        if callable(start_fn):
            try:
                start_fn(brightness_override=1, fade_in=True, fade_in_duration_s=0.25)
            except TypeError:
                start_fn()
        else:
            from src.tray.controllers.lighting_controller import start_current_effect

            start_current_effect(
                cast(LightingTrayProtocol, tray),
                brightness_override=1,
                fade_in=True,
                fade_in_duration_s=0.25,
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
            tray.engine.stop()
        except Exception:
            pass
        try:
            tray.engine.turn_off(fade=True, fade_duration_s=0.12)
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
        # Do not fight explicit user/power forced off (already gated).
        # Do not turn on lighting if it's currently off.
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
            # Pre-read effect outside the lock to minimize lock hold time
            try:
                effect = str(getattr(getattr(tray, "config", None), "effect", "none") or "none")
            except Exception:
                effect = "none"
            try:
                # Only treat the canonical SW effects as software loops.
                #
                # Note: the tray's "perkey" mode is a hardware per-key apply
                # path (not part of src.core.effects.catalog), and needs a real
                # hardware brightness write for dim-sync to actually dim the
                # keyboard.
                is_sw_effect = effect in sw_effects_set
                # For reactive typing effects, this is an overall dim-sync action.
                # Temporarily dim both the base/backdrop brightness and the
                # reactive effect brightness so the global hardware brightness
                # can drop.
                if effect in reactive_effects_set:
                    # Keep the update atomic relative to the render loop to
                    # avoid a one-frame mix of old/new brightness inputs.
                    with tray.engine.kb_lock:
                        tray.engine.per_key_brightness = dim_temp_brightness
                        _set_brightness_best_effort(
                            tray.engine,
                            dim_temp_brightness,
                            apply_to_hardware=False,
                            fade=True,
                            fade_duration_s=0.25,
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
        # Restore to current config brightness (it may have been changed while dimmed).
        # Pre-read all config values outside the lock to minimize lock hold time
        # and reduce latency before the brightness change takes effect.
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
                    # Keep the update atomic relative to the render loop to
                    # avoid a one-frame mix of old/new brightness inputs.
                    with tray.engine.kb_lock:
                        tray.engine.per_key_brightness = perkey_target
                        _set_brightness_best_effort(
                            tray.engine,
                            target,
                            apply_to_hardware=False,
                            fade=True,
                            fade_duration_s=0.25,
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
        # Only auto-restore if this wasn't an explicit user off.
        if not bool(getattr(tray, "_user_forced_off", False)) and not bool(getattr(tray, "_power_forced_off", False)):
            tray._dim_temp_active = False
            tray._dim_temp_target_brightness = None
            restore_from_idle_fn(tray)
        return
