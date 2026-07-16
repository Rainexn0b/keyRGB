"""Typed settings source resolution and defensive attribute readers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from src.core.config._settings_view import ConfigSettingsView
from src.core.utils.safe_attrs import safe_int_attr

logger = logging.getLogger(__name__)

_SETTINGS_ATTR_READ_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_SETTINGS_INT_COERCE_ERRORS = (RuntimeError,)
_SETTINGS_BOOL_COERCE_ERRORS = (RuntimeError, TypeError, ValueError)
_SETTINGS_SAFE_INT_ERRORS = (AttributeError, OverflowError, RuntimeError, TypeError, ValueError)

_DefaultT = TypeVar("_DefaultT")


class SettingsConfigLike(Protocol):
    def __getattribute__(self, name: str) -> object: ...

    def __setattr__(self, name: str, value: object) -> None: ...


SettingsSourceLike = SettingsConfigLike | ConfigSettingsView | Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ResolvedSettingsSource:
    fallback_obj: object | None
    settings_view: ConfigSettingsView | None


@dataclass(frozen=True, slots=True)
class SettingsReader:
    fallback_obj: object | None
    settings_view: ConfigSettingsView | None

    def read_bool(self, key: str, *, default: bool, fallback_attr: str | None = None) -> bool:
        attr = fallback_attr or key
        if self.settings_view is not None:
            return read_view_bool(
                self.settings_view,
                key,
                default=default,
                fallback_obj=self.fallback_obj,
                fallback_attr=attr,
            )
        if self.fallback_obj is None:
            return bool(default)
        return safe_bool(self.fallback_obj, attr, default)

    def read_int(self, key: str, *, default: int, fallback_attr: str | None = None) -> int:
        attr = fallback_attr or key
        if self.settings_view is not None:
            return read_view_int(
                self.settings_view,
                key,
                default=default,
                fallback_obj=self.fallback_obj,
                fallback_attr=attr,
            )
        if self.fallback_obj is None:
            return int(default)
        return safe_int(self.fallback_obj, attr, default)

    def read_optional_int(self, key: str, *, fallback_attr: str | None = None) -> int | None:
        attr = fallback_attr or key
        if self.settings_view is not None:
            return read_view_optional_int(
                self.settings_view,
                key,
                fallback_obj=self.fallback_obj,
                fallback_attr=attr,
            )
        if self.fallback_obj is None:
            return None
        return safe_optional_int(self.fallback_obj, attr)

    def read_optional_str(self, key: str, *, fallback_attr: str | None = None) -> str | None:
        attr = fallback_attr or key
        if self.settings_view is not None:
            return read_view_optional_str(
                self.settings_view,
                key,
                fallback_obj=self.fallback_obj,
                fallback_attr=attr,
            )
        if self.fallback_obj is None:
            return None
        return safe_optional_str(self.fallback_obj, attr)

    def read_normalized_str(self, key: str, *, default: str, fallback_attr: str | None = None) -> str:
        attr = fallback_attr or key
        if self.settings_view is not None:
            return read_view_normalized_str(
                self.settings_view,
                key,
                default=default,
                fallback_obj=self.fallback_obj,
                fallback_attr=attr,
            )
        if self.fallback_obj is None:
            return str(default).strip().lower()
        return safe_normalized_str(self.fallback_obj, attr, default)


def resolve_settings_source(config: SettingsSourceLike) -> ResolvedSettingsSource:
    if isinstance(config, ConfigSettingsView):
        return ResolvedSettingsSource(fallback_obj=None, settings_view=config)
    if isinstance(config, Mapping):
        return ResolvedSettingsSource(fallback_obj=None, settings_view=ConfigSettingsView.from_mapping(config))
    return ResolvedSettingsSource(fallback_obj=config, settings_view=settings_view_from_config(config))


def settings_view_from_config(config: SettingsConfigLike) -> ConfigSettingsView | None:
    if hasattr(config, "settings_view"):
        try:
            view_getter = getattr(config, "settings_view")
            if callable(view_getter):
                view = view_getter()
                if isinstance(view, ConfigSettingsView):
                    return view
        except _SETTINGS_ATTR_READ_ERRORS:
            logger.exception("Failed reading typed settings view from config")

    if hasattr(config, "settings"):
        try:
            raw_settings = getattr(config, "settings")
        except _SETTINGS_ATTR_READ_ERRORS:
            logger.exception("Failed reading settings mapping from config")
            return None
        if isinstance(raw_settings, ConfigSettingsView):
            return raw_settings
        if isinstance(raw_settings, Mapping):
            return ConfigSettingsView.from_mapping(raw_settings)
    return None


def read_view_bool(
    settings_view: ConfigSettingsView,
    key: str,
    *,
    default: bool,
    fallback_obj: object | None = None,
    fallback_attr: str | None = None,
) -> bool:
    if key in settings_view:
        return settings_view.read_bool(key, default)
    if fallback_obj is not None and fallback_attr is not None:
        return safe_bool(fallback_obj, fallback_attr, default)
    return default


def read_view_int(
    settings_view: ConfigSettingsView,
    key: str,
    *,
    default: int,
    fallback_obj: object | None = None,
    fallback_attr: str | None = None,
) -> int:
    if key in settings_view:
        return settings_view.read_int(key, default)
    if fallback_obj is not None and fallback_attr is not None:
        return safe_int(fallback_obj, fallback_attr, default)
    return default


def read_view_optional_int(
    settings_view: ConfigSettingsView,
    key: str,
    *,
    fallback_obj: object | None = None,
    fallback_attr: str | None = None,
) -> int | None:
    if key in settings_view:
        return settings_view.read_optional_int(key)
    if fallback_obj is not None and fallback_attr is not None:
        return safe_optional_int(fallback_obj, fallback_attr)
    return None


def read_view_optional_str(
    settings_view: ConfigSettingsView,
    key: str,
    *,
    fallback_obj: object | None = None,
    fallback_attr: str | None = None,
) -> str | None:
    if key in settings_view:
        return settings_view.read_optional_str(key)
    if fallback_obj is not None and fallback_attr is not None:
        return safe_optional_str(fallback_obj, fallback_attr)
    return None


def read_view_normalized_str(
    settings_view: ConfigSettingsView,
    key: str,
    *,
    default: str,
    fallback_obj: object | None = None,
    fallback_attr: str | None = None,
) -> str:
    if key in settings_view:
        return settings_view.read_normalized_str(key, default)
    if fallback_obj is not None and fallback_attr is not None:
        return safe_normalized_str(fallback_obj, fallback_attr, default)
    return str(default).strip().lower()


def safe_getattr_or_default(obj: object, name: str, default: _DefaultT) -> object | _DefaultT:
    try:
        return getattr(obj, name, default)
    except _SETTINGS_ATTR_READ_ERRORS:
        logger.exception("Failed reading settings attribute '%s'", name)
        return default


def coerce_int_or_fallback(value: object, *, fallback: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    except _SETTINGS_INT_COERCE_ERRORS:
        logger.exception("Failed coercing settings value to int")
        return fallback


def safe_bool(obj: object, name: str, default: bool) -> bool:
    value = safe_getattr_or_default(obj, name, default)
    try:
        return bool(value)
    except _SETTINGS_BOOL_COERCE_ERRORS:
        logger.exception("Failed coercing settings attribute '%s' to bool", name)
        return bool(default)


def safe_int(obj: object, name: str, default: int) -> int:
    default_value = coerce_int_or_fallback(default, fallback=0)
    safe_default = 0 if default_value is None else default_value
    try:
        return safe_int_attr(obj, name, default=safe_default)
    except _SETTINGS_SAFE_INT_ERRORS:
        logger.exception("Failed reading settings integer attribute '%s'", name)
        return safe_default


def safe_optional_int(obj: object, name: str) -> int | None:
    value = safe_getattr_or_default(obj, name, None)
    if value is None:
        return None
    return coerce_int_or_fallback(value, fallback=None)


def safe_optional_str(obj: object, name: str) -> str | None:
    value = safe_getattr_or_default(obj, name, None)
    if value is None:
        return None
    try:
        normalized = str(value).strip()
    except _SETTINGS_ATTR_READ_ERRORS:
        logger.exception("Failed coercing settings attribute '%s' to optional string", name)
        return None
    return normalized or None


def safe_normalized_str(obj: object, name: str, default: str) -> str:
    value = safe_getattr_or_default(obj, name, default)
    try:
        normalized = str(value or default).strip().lower()
    except _SETTINGS_ATTR_READ_ERRORS:
        logger.exception("Failed coercing settings attribute '%s' to normalized string", name)
        return str(default).strip().lower()
    return normalized or str(default).strip().lower()
