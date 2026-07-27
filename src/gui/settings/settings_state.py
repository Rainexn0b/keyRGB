"""Public settings-state facade (load/apply + clamps).

Implementation is split across:
- ``_settings_reader`` — source resolution and defensive reads
- ``_settings_scheduler`` — pure day/night scheduler helpers
- ``_settings_values`` — ``SettingsValues`` plus load/apply
"""

from __future__ import annotations

from datetime import datetime

from src.gui.settings import _settings_scheduler as settings_scheduler
from src.gui.settings import _settings_values as settings_values

# Keep a module-level datetime binding so tests can monkeypatch
# ``settings_state.datetime`` and still affect apply paths.
datetime = datetime  # noqa: PLW0127 – module-level binding for test monkeypatch

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
