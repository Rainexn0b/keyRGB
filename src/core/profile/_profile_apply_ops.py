from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Dict, Tuple, cast


KeyCell = Tuple[int, int]
_MISSING = object()
_READ_FAILED = object()
_PROFILE_APPLY_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def active_profile_name(
    *,
    default: str,
    log_key: str,
    log_msg: str,
    safe_profile_name: Callable[..., object],
    get_active_profile: Callable[..., object],
    log_throttled: Callable[..., object],
    logger: logging.Logger,
) -> str:
    try:
        return cast(str, safe_profile_name(get_active_profile()))
    except _PROFILE_APPLY_ERRORS as exc:
        log_throttled(logger, log_key, interval_s=60, level=logging.DEBUG, msg=log_msg, exc=exc)
        return default


def read_attr_value(
    obj: object,
    attr_name: str,
    *,
    log_key: str,
    log_msg: str,
    log_throttled: Callable[..., object],
    logger: logging.Logger,
) -> object:
    try:
        return getattr(obj, attr_name)
    except AttributeError:
        return _MISSING
    except _PROFILE_APPLY_ERRORS as exc:
        log_throttled(logger, log_key, interval_s=60, level=logging.DEBUG, msg=log_msg, exc=exc)
        return _READ_FAILED


def coerce_int(value: object, *, default: int) -> int:
    if value is _MISSING or value is _READ_FAILED or value is None:
        return default
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return default


def set_attr_value(
    obj: object,
    attr_name: str,
    value: int,
    *,
    log_key: str,
    log_msg: str,
    log_throttled: Callable[..., object],
    logger: logging.Logger,
) -> bool:
    try:
        setattr(obj, attr_name, int(value))
        return True
    except _PROFILE_APPLY_ERRORS as exc:
        log_throttled(logger, log_key, interval_s=60, level=logging.DEBUG, msg=log_msg, exc=exc)
        return False


def builtin_profile_brightness(name: str, *, safe_profile_name: Callable[..., object]) -> int | None:
    profile_name = safe_profile_name(name)
    if profile_name == "light":
        return 50
    if profile_name == "dim":
        return 5
    return None


def migrate_builtin_profile_brightness(
    cfg: object,
    *,
    safe_profile_name: Callable[..., object],
    get_active_profile: Callable[..., object],
    log_throttled: Callable[..., object],
    logger: logging.Logger,
) -> bool:
    profile_name = active_profile_name(
        default="",
        log_key="profiles.migrate_builtin_profile_brightness.active_profile",
        log_msg="Failed to resolve active profile during built-in brightness migration",
        safe_profile_name=safe_profile_name,
        get_active_profile=get_active_profile,
        log_throttled=log_throttled,
        logger=logger,
    )

    target = builtin_profile_brightness(profile_name, safe_profile_name=safe_profile_name)
    if target is None:
        return False

    effect_brightness = read_attr_value(
        cfg,
        "effect_brightness",
        log_key="profiles.migrate_builtin_profile_brightness.effect_brightness",
        log_msg="Failed to read effect brightness during built-in profile migration",
        log_throttled=log_throttled,
        logger=logger,
    )
    if effect_brightness is _MISSING:
        brightness = coerce_int(
            read_attr_value(
                cfg,
                "brightness",
                log_key="profiles.migrate_builtin_profile_brightness.brightness",
                log_msg="Failed to read brightness during built-in profile migration",
                log_throttled=log_throttled,
                logger=logger,
            ),
            default=0,
        )
    elif effect_brightness is _READ_FAILED:
        brightness = 0
    else:
        brightness = coerce_int(effect_brightness, default=0)

    perkey_raw = read_attr_value(
        cfg,
        "perkey_brightness",
        log_key="profiles.migrate_builtin_profile_brightness.perkey_brightness",
        log_msg="Failed to read per-key brightness during built-in profile migration",
        log_throttled=log_throttled,
        logger=logger,
    )
    perkey = coerce_int(perkey_raw, default=brightness)

    should_migrate = False
    if profile_name == "dim":
        should_migrate = perkey in {10, 15} or brightness in {10, 15} or (perkey == 5 and brightness != 5)
    elif profile_name == "light":
        should_migrate = brightness in {5, 10, 15} and perkey in {5, 10, 15}

    if not should_migrate:
        return False

    brightness_attr = "effect_brightness" if effect_brightness is not _MISSING else "brightness"
    if effect_brightness is _READ_FAILED or not set_attr_value(
        cfg,
        brightness_attr,
        target,
        log_key=f"profiles.migrate_builtin_profile_brightness.set_{brightness_attr}",
        log_msg=f"Failed to set {brightness_attr} during built-in profile migration",
        log_throttled=log_throttled,
        logger=logger,
    ):
        return False

    if perkey_raw is not _MISSING and perkey_raw is not _READ_FAILED:
        set_attr_value(
            cfg,
            "perkey_brightness",
            target,
            log_key="profiles.migrate_builtin_profile_brightness.set_perkey_brightness",
            log_msg="Failed to set per-key brightness during built-in profile migration",
            log_throttled=log_throttled,
            logger=logger,
        )
    return True


def apply_profile_to_config(
    cfg: object,
    colors: Dict[Tuple[int, int], Tuple[int, int, int]],
    *,
    safe_profile_name: Callable[..., object],
    get_active_profile: Callable[..., object],
    log_throttled: Callable[..., object],
    logger: logging.Logger,
) -> None:
    profile_name = active_profile_name(
        default="",
        log_key="profiles.apply_profile_to_config.active_profile",
        log_msg="Failed to resolve active profile while applying a profile",
        safe_profile_name=safe_profile_name,
        get_active_profile=get_active_profile,
        log_throttled=log_throttled,
        logger=logger,
    )

    def set_profile_brightness(value: int) -> None:
        effect_brightness = read_attr_value(
            cfg,
            "effect_brightness",
            log_key="profiles.apply_profile_to_config.effect_brightness",
            log_msg="Failed to read effect brightness while applying a profile",
            log_throttled=log_throttled,
            logger=logger,
        )
        if effect_brightness is _MISSING:
            set_attr_value(
                cfg,
                "brightness",
                value,
                log_key="profiles.apply_profile_to_config.set_brightness",
                log_msg="Failed to set brightness while applying a profile",
                log_throttled=log_throttled,
                logger=logger,
            )
        elif effect_brightness is not _READ_FAILED:
            set_attr_value(
                cfg,
                "effect_brightness",
                value,
                log_key="profiles.apply_profile_to_config.set_effect_brightness",
                log_msg="Failed to set effect brightness while applying a profile",
                log_throttled=log_throttled,
                logger=logger,
            )

        perkey_brightness = read_attr_value(
            cfg,
            "perkey_brightness",
            log_key="profiles.apply_profile_to_config.perkey_brightness",
            log_msg="Failed to read per-key brightness while applying a profile",
            log_throttled=log_throttled,
            logger=logger,
        )
        if perkey_brightness is not _MISSING and perkey_brightness is not _READ_FAILED:
            set_attr_value(
                cfg,
                "perkey_brightness",
                value,
                log_key="profiles.apply_profile_to_config.set_perkey_brightness",
                log_msg="Failed to set per-key brightness while applying a profile",
                log_throttled=log_throttled,
                logger=logger,
            )

    perkey_brightness = read_attr_value(
        cfg,
        "perkey_brightness",
        log_key="profiles.apply_profile_to_config.read_perkey_brightness",
        log_msg="Failed to read per-key brightness while applying a profile",
        log_throttled=log_throttled,
        logger=logger,
    )
    if perkey_brightness is _MISSING:
        perkey_value = coerce_int(
            read_attr_value(
                cfg,
                "brightness",
                log_key="profiles.apply_profile_to_config.read_brightness",
                log_msg="Failed to read brightness while applying a profile",
                log_throttled=log_throttled,
                logger=logger,
            ),
            default=0,
        )
    elif perkey_brightness is _READ_FAILED:
        perkey_value = 0
    else:
        perkey_value = coerce_int(perkey_brightness, default=0)

    if perkey_value <= 0:
        if hasattr(cfg, "perkey_brightness"):
            cfg.perkey_brightness = 50
        else:
            cfg.brightness = 50  # type: ignore[attr-defined]

    builtin_target = builtin_profile_brightness(profile_name, safe_profile_name=safe_profile_name)
    if builtin_target is not None:
        set_profile_brightness(builtin_target)
    cfg.effect = "perkey"  # type: ignore[attr-defined]
    cfg.per_key_colors = colors  # type: ignore[attr-defined]
