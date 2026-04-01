from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Optional

from src.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET as SW_EFFECTS
from src.core.effects.catalog import is_forced_hardware_effect, resolve_effect_name_for_backend, strip_effect_namespace
from src.core.utils.safe_attrs import safe_int_attr, safe_str_attr
from src.tray.protocols import LightingTrayProtocol


REACTIVE_EFFECTS_SET = frozenset(REACTIVE_EFFECTS)
logger = logging.getLogger(__name__)
_ENGINE_FALLBACK_UNSET = object()


def _log_module_exception(msg: str, exc: Exception) -> None:
    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _log_tray_exception(tray: LightingTrayProtocol, msg: str, exc: Exception) -> None:
    log_exception = getattr(tray, "_log_exception", None)
    if callable(log_exception):
        try:
            log_exception(msg, exc)
            return
        except Exception as log_exc:
            _log_module_exception("Tray exception logger failed: %s", log_exc)
    _log_module_exception(msg, exc)


def _set_engine_attr_best_effort(
    tray: LightingTrayProtocol,
    attr: str,
    value: object,
    *,
    error_msg: str,
    fallback: object = _ENGINE_FALLBACK_UNSET,
) -> None:
    engine = getattr(tray, "engine", None)
    try:
        setattr(engine, attr, value)
        return
    except AttributeError:
        return
    except Exception as exc:
        _log_tray_exception(tray, error_msg, exc)

    if fallback is _ENGINE_FALLBACK_UNSET:
        return

    try:
        setattr(engine, attr, fallback)
    except AttributeError:
        return
    except Exception as exc:
        _log_tray_exception(tray, f"Failed to reset engine attribute '{attr}': %s", exc)


def _coerce_brightness_override(brightness_override: object) -> int:
    try:
        return int(brightness_override)
    except (TypeError, ValueError, OverflowError):
        return 0


def _config_per_key_colors_ref(config: object) -> Mapping[object, object] | None:
    try:
        colors = getattr(config, "per_key_colors", None)
    except AttributeError:
        return None
    except Exception as exc:
        _log_module_exception("Failed reading config per-key colors: %s", exc)
        return None
    if isinstance(colors, Mapping) and colors:
        return colors
    return None


def parse_menu_int(item: object) -> Optional[int]:
    try:
        s = str(item)
    except Exception as exc:
        _log_module_exception("Failed parsing tray menu integer item: %s", exc)
        return None

    s = s.replace("🔘", "").replace("⚪", "").strip()
    try:
        return int(s)
    except (TypeError, ValueError, OverflowError):
        return None


def try_log_event(tray: LightingTrayProtocol, source: str, action: str, **fields: object) -> None:
    log_event = getattr(tray, "_log_event", None)
    if not callable(log_event):
        return
    try:
        log_event(source, action, **fields)
    except Exception as exc:
        _log_module_exception("Tray event logging failed: %s", exc)


def get_effect_name(tray: LightingTrayProtocol) -> str:
    effect = safe_str_attr(getattr(tray, "config", None), "effect", default="none") or "none"
    try:
        return resolve_effect_name_for_backend(effect, getattr(tray, "backend", None))
    except Exception as exc:
        _log_tray_exception(tray, "Failed to resolve current effect name: %s", exc)
        return "none"


def is_software_effect(effect: str) -> bool:
    if is_forced_hardware_effect(effect):
        return False
    return strip_effect_namespace(effect) in SW_EFFECTS


def is_reactive_effect(effect: str) -> bool:
    return strip_effect_namespace(effect) in REACTIVE_EFFECTS_SET


def ensure_device_best_effort(tray: LightingTrayProtocol) -> None:
    ensure = getattr(getattr(tray, "engine", None), "_ensure_device_available", None)
    if callable(ensure):
        ensure()


def set_engine_perkey_from_config_for_sw_effect(tray: LightingTrayProtocol) -> None:
    _set_engine_attr_best_effort(
        tray,
        "per_key_colors",
        _config_per_key_colors_ref(tray.config),
        error_msg="Failed to apply per-key colors to engine: %s",
        fallback=None,
    )
    _set_engine_attr_best_effort(
        tray,
        "per_key_brightness",
        safe_int_attr(tray.config, "perkey_brightness", default=0),
        error_msg="Failed to apply per-key brightness to engine: %s",
        fallback=None,
    )


def clear_engine_perkey_state(tray: LightingTrayProtocol) -> None:
    _set_engine_attr_best_effort(
        tray,
        "per_key_colors",
        None,
        error_msg="Failed to clear engine per-key colors: %s",
    )
    _set_engine_attr_best_effort(
        tray,
        "per_key_brightness",
        None,
        error_msg="Failed to clear engine per-key brightness: %s",
    )


def apply_perkey_mode(tray: LightingTrayProtocol, *, brightness_override: Optional[int] = None) -> None:
    tray.engine.stop()
    if brightness_override is not None:
        effective_brightness = _coerce_brightness_override(brightness_override)
    else:
        effective_brightness = safe_int_attr(tray.config, "brightness", default=0)
    if int(effective_brightness) == 0:
        tray.engine.turn_off()
        tray.is_off = True
        return

    _set_engine_attr_best_effort(
        tray,
        "per_key_colors",
        _config_per_key_colors_ref(tray.config),
        error_msg="Failed to apply per-key colors to engine: %s",
        fallback=None,
    )
    _set_engine_attr_best_effort(
        tray,
        "per_key_brightness",
        safe_int_attr(
            tray.config,
            "perkey_brightness",
            default=safe_int_attr(tray.config, "brightness", default=0),
        ),
        error_msg="Failed to apply per-key brightness to engine: %s",
        fallback=None,
    )

    with tray.engine.kb_lock:
        enable_user_mode = getattr(tray.engine.kb, "enable_user_mode", None)
        if callable(enable_user_mode):
            try:
                enable_user_mode(brightness=effective_brightness, save=True)
            except TypeError:
                try:
                    enable_user_mode(brightness=effective_brightness)
                except Exception as exc:
                    _log_tray_exception(tray, "Failed to enable per-key user mode: %s", exc)
            except Exception as exc:
                _log_tray_exception(tray, "Failed to enable per-key user mode: %s", exc)
        tray.engine.kb.set_key_colors(
            tray.config.per_key_colors,
            brightness=effective_brightness,
            enable_user_mode=True,
        )

    tray.is_off = False


def apply_uniform_none_mode(tray: LightingTrayProtocol, *, brightness_override: Optional[int] = None) -> None:
    tray.engine.stop()
    if brightness_override is not None:
        effective_brightness = _coerce_brightness_override(brightness_override)
    else:
        effective_brightness = safe_int_attr(tray.config, "brightness", default=0)
    if int(effective_brightness) == 0:
        tray.engine.turn_off()
        tray.is_off = True
        return

    clear_engine_perkey_state(tray)

    with tray.engine.kb_lock:
        tray.engine.kb.set_color(tray.config.color, brightness=effective_brightness)

    tray.is_off = False
