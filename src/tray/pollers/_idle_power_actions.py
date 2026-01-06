from __future__ import annotations

from typing import Any, Callable, Optional


def restore_from_idle(tray: Any) -> None:
    tray.is_off = False
    tray._idle_forced_off = False

    # Best-effort: if brightness is 0, fall back to last brightness.
    try:
        if int(getattr(tray.config, "brightness", 0) or 0) == 0:
            tray.config.brightness = int(getattr(tray, "_last_brightness", 25) or 25)
    except Exception:
        pass

    try:
        tray._start_current_effect()
    except Exception:
        try:
            tray._log_exception("Failed to restore lighting after idle", Exception("restore failed"))
        except Exception:
            pass

    try:
        tray._refresh_ui()
    except Exception:
        pass


def apply_idle_action(
    tray: Any,
    *,
    action: Optional[str],
    dim_temp_brightness: int,
    restore_from_idle_fn: Callable[[Any], None],
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
            tray.engine.turn_off()
        except Exception:
            pass

        tray.is_off = True
        tray._idle_forced_off = True
        try:
            tray._refresh_ui()
        except Exception:
            pass
        return

    if action == "dim_to_temp":
        # Do not fight explicit user/power forced off (already gated).
        # Do not turn on lighting if it's currently off.
        if not bool(getattr(tray, "is_off", False)):
            tray._dim_temp_active = True
            tray._dim_temp_target_brightness = int(dim_temp_brightness)
            try:
                effect = str(getattr(getattr(tray, "config", None), "effect", "none") or "none")
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
                    try:
                        tray.engine.per_key_brightness = int(dim_temp_brightness)
                    except Exception:
                        pass
                tray.engine.set_brightness(int(dim_temp_brightness), apply_to_hardware=not is_sw_effect)
            except Exception:
                pass
        return

    if action == "restore_brightness":
        tray._dim_temp_active = False
        tray._dim_temp_target_brightness = None
        # Restore to current config brightness (it may have been changed while dimmed).
        try:
            target = int(getattr(tray.config, "brightness", 0) or 0)
        except Exception:
            target = 0
        if target > 0 and not bool(getattr(tray, "is_off", False)):
            try:
                effect = str(getattr(getattr(tray, "config", None), "effect", "none") or "none")
                is_sw_effect = effect in sw_effects_set
                if effect in reactive_effects_set:
                    try:
                        tray.engine.per_key_brightness = int(getattr(tray.config, "perkey_brightness", 0) or 0)
                    except Exception:
                        pass
                tray.engine.set_brightness(int(target), apply_to_hardware=not is_sw_effect)
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
