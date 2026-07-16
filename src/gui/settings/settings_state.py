"""Public settings-state facade (load/apply + clamps).

Implementation is split across:
- ``_settings_reader`` — source resolution and defensive reads
- ``_settings_scheduler`` — pure day/night scheduler helpers
- ``_settings_values`` — ``SettingsValues`` plus load/apply
"""

from __future__ import annotations

from datetime import datetime

from src.gui.settings import _settings_reader as settings_reader
from src.gui.settings import _settings_scheduler as settings_scheduler
from src.gui.settings import _settings_values as settings_values

# Keep a module-level datetime binding so tests can monkeypatch
# ``settings_state.datetime`` and still affect apply paths.
datetime = datetime

# Compatibility re-exports for tests and internal helpers.
_SettingsConfigLike = settings_reader.SettingsConfigLike
_SettingsSourceLike = settings_reader.SettingsSourceLike
_ResolvedSettingsSource = settings_reader.ResolvedSettingsSource
_SettingsReader = settings_reader.SettingsReader
_SETTINGS_ATTR_READ_ERRORS = settings_reader._SETTINGS_ATTR_READ_ERRORS
_SETTINGS_INT_COERCE_ERRORS = settings_reader._SETTINGS_INT_COERCE_ERRORS
_SETTINGS_BOOL_COERCE_ERRORS = settings_reader._SETTINGS_BOOL_COERCE_ERRORS
_SETTINGS_SAFE_INT_ERRORS = settings_reader._SETTINGS_SAFE_INT_ERRORS

SettingsValues = settings_values.SettingsValues
clamp_brightness = settings_values.clamp_brightness
clamp_nonzero_brightness = settings_values.clamp_nonzero_brightness
load_settings_values = settings_values.load_settings_values


def apply_settings_values_to_config(*, config, values: SettingsValues) -> None:
    """Facade apply path; uses this module's ``datetime`` for monkeypatch seams."""

    settings_values.apply_settings_values_to_config(
        config=config,
        values=values,
        now=datetime.now(),
    )


_resolve_settings_source = settings_reader.resolve_settings_source
_settings_view_from_config = settings_reader.settings_view_from_config
_read_view_bool = settings_reader.read_view_bool
_read_view_int = settings_reader.read_view_int
_read_view_optional_int = settings_reader.read_view_optional_int
_read_view_optional_str = settings_reader.read_view_optional_str
_read_view_normalized_str = settings_reader.read_view_normalized_str
_safe_getattr_or_default = settings_reader.safe_getattr_or_default
_coerce_int_or_fallback = settings_reader.coerce_int_or_fallback
_safe_bool = settings_reader.safe_bool
_safe_int = settings_reader.safe_int
_safe_optional_int = settings_reader.safe_optional_int
_safe_optional_str = settings_reader.safe_optional_str
_safe_normalized_str = settings_reader.safe_normalized_str
_normalize_optional_power_mode = settings_values.normalize_optional_power_mode
_load_scheduler_brightness = settings_values.load_scheduler_brightness
_parse_scheduler_time = settings_scheduler.parse_scheduler_time
_is_scheduler_night = settings_scheduler.is_scheduler_night


def _active_scheduler_reactive_brightness(values: SettingsValues, *, now: datetime) -> int | None:
    return settings_scheduler.active_scheduler_reactive_brightness(
        values,
        now=now,
        clamp_brightness=clamp_brightness,
    )


__all__ = [
    "SettingsValues",
    "apply_settings_values_to_config",
    "clamp_brightness",
    "clamp_nonzero_brightness",
    "load_settings_values",
]
