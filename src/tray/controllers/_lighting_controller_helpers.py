from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Optional, TypeVar

from src.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET as SW_EFFECTS
from src.core.effects.catalog import is_forced_hardware_effect, resolve_effect_name_for_backend, strip_effect_namespace
from src.core.effects.perkey_animation import per_key_mode_requires_frame_reassert
from src.core.effects.perkey_animation import restore_hidden_per_key_rows_once
from src.core.lighting_layers import resolve_render_effect
from src.core.utils.safe_attrs import safe_int_attr, safe_str_attr
from src.tray.protocols import (
    LightingTrayProtocol,
    clear_idle_power_state_field,
    read_idle_power_state_optional_bool_field,
    read_idle_power_state_optional_int_field,
)


REACTIVE_EFFECTS_SET = frozenset(REACTIVE_EFFECTS)
logger = logging.getLogger(__name__)
_T = TypeVar("_T")
_ENGINE_FALLBACK_UNSET = object()
_RECOVERABLE_CONFIG_READ_EXCEPTIONS = (OSError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_ENGINE_ATTR_EXCEPTIONS = (OSError, OverflowError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_EFFECT_NAME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_ENABLE_USER_MODE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_TRAY_LOGGING_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_STRINGIFICATION_EXCEPTIONS = (LookupError, OSError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def _log_module_exception(msg: str, exc: Exception) -> None:
    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _run_diagnostic_boundary(
    action: Callable[[], _T],
    *,
    runtime_exceptions: tuple[type[Exception], ...],
    on_recoverable: Callable[[Exception], _T],
) -> _T:
    try:
        return action()
    except runtime_exceptions as exc:  # @quality-exception exception-transparency: diagnostic-only helper callbacks and stringification cross runtime/user seams and must stay best-effort for recoverable failures
        return on_recoverable(exc)


def _log_tray_exception(tray: LightingTrayProtocol, msg: str, exc: Exception) -> None:
    def _recover_tray_logging(log_exc: Exception) -> None:
        logger.exception("Tray exception logger failed while logging boundary: %s", log_exc)
        _log_module_exception(msg, exc)

    _run_diagnostic_boundary(
        lambda: tray._log_exception(msg, exc),
        runtime_exceptions=_RECOVERABLE_TRAY_LOGGING_EXCEPTIONS,
        on_recoverable=_recover_tray_logging,
    )


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
    except _RECOVERABLE_ENGINE_ATTR_EXCEPTIONS as exc:
        _log_tray_exception(tray, error_msg, exc)

    if fallback is _ENGINE_FALLBACK_UNSET:
        return

    try:
        setattr(engine, attr, fallback)
    except AttributeError:
        return
    except _RECOVERABLE_ENGINE_ATTR_EXCEPTIONS as exc:
        _log_tray_exception(tray, f"Failed to reset engine attribute '{attr}': %s", exc)


def _coerce_brightness_override(brightness_override: object) -> int:
    try:
        return int(brightness_override)  # type: ignore[call-overload]
    except (TypeError, ValueError, OverflowError):
        return 0


def _config_per_key_colors_ref(config: object) -> Mapping[object, object] | None:
    try:
        colors = getattr(config, "per_key_colors", None)
    except AttributeError:
        return None
    except _RECOVERABLE_CONFIG_READ_EXCEPTIONS as exc:
        _log_module_exception("Failed reading config per-key colors: %s", exc)
        return None
    if isinstance(colors, Mapping) and colors:
        return colors
    return None


def parse_menu_int(item: object) -> Optional[int]:
    def _stringify_item() -> str | None:
        return str(item)

    def _recover_stringification(exc: Exception) -> str | None:
        _log_module_exception("Failed parsing tray menu integer item: %s", exc)
        return None

    s = _run_diagnostic_boundary(
        _stringify_item,
        runtime_exceptions=_RECOVERABLE_STRINGIFICATION_EXCEPTIONS,
        on_recoverable=_recover_stringification,
    )
    if s is None:
        return None

    s = s.replace("🔘", "").replace("⚪", "").strip()
    try:
        return int(s)
    except (TypeError, ValueError, OverflowError):
        return None


def try_log_event(tray: LightingTrayProtocol, source: str, action: str, **fields: object) -> None:
    _run_diagnostic_boundary(
        lambda: tray._log_event(source, action, **fields),
        runtime_exceptions=_RECOVERABLE_TRAY_LOGGING_EXCEPTIONS,
        on_recoverable=lambda exc: _log_module_exception("Tray event logging failed: %s", exc),
    )


def get_effect_name(tray: LightingTrayProtocol) -> str:
    engine_effect = None
    try:
        engine_effect = getattr(getattr(tray, "engine", None), "current_effect", None)
    except _RECOVERABLE_EFFECT_NAME_EXCEPTIONS as exc:
        _log_tray_exception(tray, "Failed to read current engine effect name: %s", exc)

    if isinstance(engine_effect, str) and engine_effect.strip():
        effect = engine_effect
    else:
        config = getattr(tray, "config", None)
        effect = resolve_render_effect(
            selected_effect=safe_str_attr(config, "effect", default="none") or "none",
            per_key_colors=getattr(config, "per_key_colors", None),
            resolve_effect_name_fn=lambda effect_name: resolve_effect_name_for_backend(
                effect_name,
                getattr(tray, "backend", None),
            ),
        )
    try:
        return resolve_effect_name_for_backend(effect, getattr(tray, "backend", None))
    except _RECOVERABLE_EFFECT_NAME_EXCEPTIONS as exc:
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


def _perkey_backend_requires_reassert(tray: LightingTrayProtocol) -> bool:
    try:
        kb = getattr(getattr(tray, "engine", None), "kb", None)
        return bool(per_key_mode_requires_frame_reassert(kb))
    except _RECOVERABLE_ENABLE_USER_MODE_EXCEPTIONS:
        return False


def sync_reactive_effect_brightness_state(
    tray: LightingTrayProtocol,
    *,
    source: str,
    base_brightness: int | None = None,
    reactive_brightness: int | None = None,
    fade: bool | None = None,
    fade_duration_s: float | None = None,
) -> None:
    if base_brightness is None and reactive_brightness is None:
        return

    try:
        with tray.engine.kb_lock:
            if base_brightness is not None:
                try:
                    tray.engine.per_key_brightness = int(base_brightness)
                except _RECOVERABLE_ENGINE_ATTR_EXCEPTIONS as exc:
                    _log_tray_exception(
                        tray,
                        f"Failed to sync {source} reactive engine per-key brightness: %s",
                        exc,
                    )
            if reactive_brightness is not None:
                try:
                    tray.engine.reactive_brightness = int(reactive_brightness)
                except _RECOVERABLE_ENGINE_ATTR_EXCEPTIONS as exc:
                    _log_tray_exception(
                        tray,
                        f"Failed to sync {source} reactive engine pulse brightness: %s",
                        exc,
                    )
            if base_brightness is None:
                return

            try:
                if fade is None:
                    tray.engine.set_brightness(
                        int(base_brightness),
                        apply_to_hardware=False,
                    )
                elif fade_duration_s is None:
                    tray.engine.set_brightness(
                        int(base_brightness),
                        apply_to_hardware=False,
                        fade=bool(fade),
                    )
                else:
                    tray.engine.set_brightness(
                        int(base_brightness),
                        apply_to_hardware=False,
                        fade=bool(fade),
                        fade_duration_s=float(fade_duration_s),
                    )
            except _RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS as exc:
                _log_tray_exception(
                    tray,
                    f"Failed to apply {source} reactive brightness: %s",
                    exc,
                )
    except _RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS as exc:
        _log_tray_exception(
            tray,
            f"Failed to enter {source} reactive engine update boundary: %s",
            exc,
        )


def apply_perkey_mode(
    tray: LightingTrayProtocol,
    *,
    brightness_override: Optional[int] = None,
    reassert_user_mode: bool = True,
) -> None:
    def _clear_hidden_restore_hints() -> None:
        clear_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_brightness_hint",
            state_name="hidden_perkey_restore_brightness_hint",
            value=None,
        )
        clear_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_device_off_hint",
            state_name="hidden_perkey_restore_device_off_hint",
            value=None,
        )

    should_reassert_user_mode = bool(reassert_user_mode) or _perkey_backend_requires_reassert(tray)
    should_pre_enable_user_mode = bool(reassert_user_mode)
    if brightness_override is not None:
        effective_brightness = _coerce_brightness_override(brightness_override)
    else:
        effective_brightness = safe_int_attr(tray.config, "brightness", default=0)
    if int(effective_brightness) == 0:
        if should_reassert_user_mode:
            tray.engine.stop()
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
    if (
        should_reassert_user_mode
        and not should_pre_enable_user_mode
        and restore_hidden_per_key_rows_once(
            kb=tray.engine.kb,
            kb_lock=tray.engine.kb_lock,
            color_map=tray.config.per_key_colors,
            brightness=int(effective_brightness),
            known_brightness=read_idle_power_state_optional_int_field(
                tray,
                attr_name="_hidden_perkey_restore_brightness_hint",
                state_name="hidden_perkey_restore_brightness_hint",
                default=None,
            ),
            known_is_off=read_idle_power_state_optional_bool_field(
                tray,
                attr_name="_hidden_perkey_restore_device_off_hint",
                state_name="hidden_perkey_restore_device_off_hint",
                default=None,
            ),
        )
    ):
        _clear_hidden_restore_hints()
        tray.is_off = False
        return

    _clear_hidden_restore_hints()

    if should_reassert_user_mode:
        tray.engine.stop()

    with tray.engine.kb_lock:
        if should_pre_enable_user_mode:
            enable_user_mode = getattr(tray.engine.kb, "enable_user_mode", None)
            if callable(enable_user_mode):
                try:
                    enable_user_mode(brightness=effective_brightness, save=True)
                except TypeError:
                    try:
                        enable_user_mode(brightness=effective_brightness)
                    except _RECOVERABLE_ENABLE_USER_MODE_EXCEPTIONS as exc:
                        _log_tray_exception(tray, "Failed to enable per-key user mode: %s", exc)
                except _RECOVERABLE_ENABLE_USER_MODE_EXCEPTIONS as exc:
                    _log_tray_exception(tray, "Failed to enable per-key user mode: %s", exc)
        tray.engine.kb.set_key_colors(
            tray.config.per_key_colors,
            brightness=effective_brightness,
            enable_user_mode=should_reassert_user_mode,
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
