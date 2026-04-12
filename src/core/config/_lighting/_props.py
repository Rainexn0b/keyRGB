from __future__ import annotations

import logging
from typing import Iterable


logger = logging.getLogger(__name__)
_RECOVERABLE_INT_COERCION_EXCEPTIONS = (TypeError, ValueError, OverflowError)
_CONFIG_HELPER_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _log_config_exception(message: str, exc: Exception) -> None:
    logger.error(message, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _read_setting(settings: object, key: str, default: object) -> object:
    try:
        return settings.get(key, default)  # type: ignore[attr-defined]
    except _CONFIG_HELPER_RUNTIME_ERRORS as exc:
        _log_config_exception(f"Failed reading config setting {key}: %s", exc)
        return default


def _coerce_bool(value: object, *, default: bool) -> bool:
    try:
        return bool(value)
    except _CONFIG_HELPER_RUNTIME_ERRORS as exc:
        _log_config_exception("Failed coercing config bool value: %s", exc)
        return bool(default)


def _coerce_int(value: object, *, default: int) -> int:
    try:
        return int(value)  # type: ignore[call-overload]
    except _RECOVERABLE_INT_COERCION_EXCEPTIONS:
        return int(default)
    except _CONFIG_HELPER_RUNTIME_ERRORS as exc:
        _log_config_exception("Failed coercing config int value: %s", exc)
        return int(default)


def _normalize_optional_brightness(owner: object, value: object) -> int | None:
    if value is None:
        return None
    try:
        return owner._normalize_brightness_value(value)  # type: ignore[attr-defined]
    except _RECOVERABLE_INT_COERCION_EXCEPTIONS:
        return None
    except _CONFIG_HELPER_RUNTIME_ERRORS as exc:
        _log_config_exception("Failed normalizing optional brightness value: %s", exc)
        return None


def bool_prop(key: str, *, default: bool) -> property:
    def _get(self) -> bool:
        return _coerce_bool(_read_setting(self._settings, key, default), default=default)

    def _set(self, value: bool) -> None:
        self._settings[key] = bool(value)
        self._save()

    return property(_get, _set)


def int_prop(key: str, *, default: int, min_v: int | None = None, max_v: int | None = None) -> property:
    def _get(self) -> int:
        v = _coerce_int(_read_setting(self._settings, key, default) or 0, default=default)
        if min_v is not None:
            v = max(int(min_v), v)
        if max_v is not None:
            v = min(int(max_v), v)
        return v

    def _set(self, value: int) -> None:
        v = _coerce_int(value, default=default)
        if min_v is not None:
            v = max(int(min_v), v)
        if max_v is not None:
            v = min(int(max_v), v)
        self._settings[key] = v
        self._save()

    return property(_get, _set)


def enum_prop(key: str, *, default: str, allowed: Iterable[str]) -> property:
    allowed_set = {str(x).strip().lower() for x in allowed}
    default_norm = str(default or "").strip().lower()
    if default_norm not in allowed_set:
        default_norm = next(iter(allowed_set)) if allowed_set else ""

    def _get(self) -> str:
        v = str(self._settings.get(key, default_norm) or default_norm).strip().lower()
        return v if v in allowed_set else default_norm

    def _set(self, value: str) -> None:
        v = str(value or default_norm).strip().lower()
        self._settings[key] = v if v in allowed_set else default_norm
        self._save()

    return property(_get, _set)


def optional_brightness_prop(key: str) -> property:
    def _get(self) -> int | None:
        return _normalize_optional_brightness(self, _read_setting(self._settings, key, None))

    def _set(self, value: int | None) -> None:
        if value is None:
            self._settings[key] = None
        else:
            self._settings[key] = self._normalize_brightness_value(value)
        self._save()

    return property(_get, _set)
