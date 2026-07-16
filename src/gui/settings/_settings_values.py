"""SettingsValues model plus pure load/apply helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.core.power.system import PowerMode
from src.core.resources.layouts.catalog import VALID_LAYOUT_IDS
from src.gui.settings import _settings_reader as settings_reader
from src.gui.settings import _settings_scheduler as settings_scheduler


def clamp_brightness(value: int) -> int:
    return max(0, min(50, int(value)))


def clamp_nonzero_brightness(value: int, *, default: int = 5) -> int:
    v = settings_reader.coerce_int_or_fallback(value, fallback=None)
    if v is None:
        fallback_value = settings_reader.coerce_int_or_fallback(default, fallback=5)
        v = 5 if fallback_value is None else fallback_value
    return max(1, min(50, v))


def normalize_optional_power_mode(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    try:
        return PowerMode(normalized).value
    except ValueError:
        return None


def load_scheduler_brightness(
    reader: settings_reader.SettingsReader,
    *,
    key: str,
    live_default: int,
) -> int:
    if reader.settings_view is not None:
        if key in reader.settings_view:
            return clamp_brightness(reader.settings_view.read_int(key, live_default))
        return clamp_brightness(live_default)

    if reader.fallback_obj is not None:
        explicit_value = settings_reader.safe_optional_int(reader.fallback_obj, key)
        if explicit_value is not None:
            return clamp_brightness(explicit_value)

    return clamp_brightness(live_default)


@dataclass(frozen=True, slots=True)
class SettingsValues:
    power_management_enabled: bool
    power_off_on_suspend: bool
    power_off_on_lid_close: bool
    power_restore_on_resume: bool
    power_restore_on_lid_open: bool

    autostart: bool
    experimental_backends_enabled: bool

    ac_lighting_enabled: bool
    battery_lighting_enabled: bool
    ac_lighting_brightness: int
    battery_lighting_brightness: int
    ac_power_mode: str | None
    battery_power_mode: str | None

    screen_dim_sync_enabled: bool
    # 'off' | 'temp'
    screen_dim_sync_mode: str
    # 1-50 (same brightness scale as `brightness`). Only used when mode == 'temp'.
    screen_dim_temp_brightness: int

    # Debounce polls for idle-power dimming decisions (each poll = 0.5s).
    idle_dim_debounce_enter_polls: int
    idle_dim_debounce_exit_polls: int

    time_scheduler_enabled: bool
    day_start_time: str
    night_start_time: str
    day_base_brightness: int
    day_reactive_brightness: int
    night_base_brightness: int
    night_reactive_brightness: int

    os_autostart_enabled: bool

    # Physical keyboard layout for per-key editor / calibrator overlay.
    # Canonical values come from src.core.resources.layouts.catalog.
    physical_layout: str = "auto"


def load_settings_values(*, config: settings_reader.SettingsSourceLike, os_autostart_enabled: bool) -> SettingsValues:
    """Best-effort load of GUI settings from a Config-like object.

    This is intentionally pure (no Tk, no filesystem) and defensive.
    """

    source = settings_reader.resolve_settings_source(config)
    reader = settings_reader.SettingsReader(fallback_obj=source.fallback_obj, settings_view=source.settings_view)

    base_brightness = clamp_brightness(reader.read_int("brightness", default=25))
    reactive_brightness = clamp_brightness(reader.read_int("reactive_brightness", default=base_brightness))
    bs_enabled = reader.read_bool("battery_saver_enabled", default=False)
    bs_brightness = reader.read_int("battery_saver_brightness", default=25)

    ac_override = reader.read_optional_int("ac_lighting_brightness")
    batt_override = reader.read_optional_int("battery_lighting_brightness")
    ac_power_mode = normalize_optional_power_mode(reader.read_optional_str("ac_power_mode"))
    battery_power_mode = normalize_optional_power_mode(reader.read_optional_str("battery_power_mode"))

    power_management_enabled = reader.read_bool(
        "power_management_enabled",
        default=reader.read_bool("management_enabled", default=True),
    )
    autostart = reader.read_bool("autostart", default=True)
    experimental_backends_enabled = reader.read_bool("experimental_backends_enabled", default=False)
    ac_lighting_enabled = reader.read_bool("ac_lighting_enabled", default=True)
    battery_lighting_enabled = reader.read_bool("battery_lighting_enabled", default=True)
    screen_dim_sync_enabled = reader.read_bool("screen_dim_sync_enabled", default=True)
    screen_dim_sync_mode = reader.read_normalized_str("screen_dim_sync_mode", default="off")
    screen_dim_temp_brightness = clamp_nonzero_brightness(
        reader.read_int("screen_dim_temp_brightness", default=5),
        default=5,
    )
    idle_dim_debounce_enter_polls = max(
        1,
        min(60, reader.read_int("idle_dim_debounce_enter_polls", default=6)),
    )
    idle_dim_debounce_exit_polls = max(
        1,
        min(60, reader.read_int("idle_dim_debounce_exit_polls", default=10)),
    )

    time_scheduler_enabled = reader.read_bool("time_scheduler_enabled", default=False)
    day_start_time = reader.read_normalized_str("day_start_time", default="08:00")
    night_start_time = reader.read_normalized_str("night_start_time", default="20:00")
    day_base_brightness = load_scheduler_brightness(
        reader,
        key="day_base_brightness",
        live_default=base_brightness,
    )
    day_reactive_brightness = load_scheduler_brightness(
        reader,
        key="day_reactive_brightness",
        live_default=reactive_brightness,
    )
    night_base_brightness = load_scheduler_brightness(
        reader,
        key="night_base_brightness",
        live_default=base_brightness,
    )
    night_reactive_brightness = load_scheduler_brightness(
        reader,
        key="night_reactive_brightness",
        live_default=reactive_brightness,
    )

    physical_layout = reader.read_normalized_str("physical_layout", default="auto")

    ac_brightness = ac_override if ac_override is not None else base_brightness

    if batt_override is not None:
        batt_brightness = batt_override
    else:
        batt_brightness = bs_brightness if bs_enabled else base_brightness

    return SettingsValues(
        power_management_enabled=power_management_enabled,
        power_off_on_suspend=reader.read_bool("power_off_on_suspend", default=True),
        power_off_on_lid_close=reader.read_bool("power_off_on_lid_close", default=True),
        power_restore_on_resume=reader.read_bool("power_restore_on_resume", default=True),
        power_restore_on_lid_open=reader.read_bool("power_restore_on_lid_open", default=True),
        autostart=autostart,
        experimental_backends_enabled=experimental_backends_enabled,
        ac_lighting_enabled=ac_lighting_enabled,
        battery_lighting_enabled=battery_lighting_enabled,
        ac_lighting_brightness=clamp_brightness(ac_brightness),
        battery_lighting_brightness=clamp_brightness(batt_brightness),
        ac_power_mode=ac_power_mode,
        battery_power_mode=battery_power_mode,
        screen_dim_sync_enabled=screen_dim_sync_enabled,
        screen_dim_sync_mode=screen_dim_sync_mode,
        screen_dim_temp_brightness=screen_dim_temp_brightness,
        idle_dim_debounce_enter_polls=idle_dim_debounce_enter_polls,
        idle_dim_debounce_exit_polls=idle_dim_debounce_exit_polls,
        time_scheduler_enabled=time_scheduler_enabled,
        day_start_time=day_start_time,
        night_start_time=night_start_time,
        day_base_brightness=day_base_brightness,
        day_reactive_brightness=day_reactive_brightness,
        night_base_brightness=night_base_brightness,
        night_reactive_brightness=night_reactive_brightness,
        os_autostart_enabled=bool(os_autostart_enabled),
        physical_layout=physical_layout,
    )


def apply_settings_values_to_config(
    *,
    config: settings_reader.SettingsConfigLike,
    values: SettingsValues,
    now: datetime | None = None,
) -> None:
    """Apply GUI settings back onto a Config-like object."""

    config.power_management_enabled = bool(values.power_management_enabled)
    config.management_enabled = bool(values.power_management_enabled)
    config.power_off_on_suspend = bool(values.power_off_on_suspend)
    config.power_off_on_lid_close = bool(values.power_off_on_lid_close)
    config.power_restore_on_resume = bool(values.power_restore_on_resume)
    config.power_restore_on_lid_open = bool(values.power_restore_on_lid_open)

    config.autostart = bool(values.autostart)
    config.experimental_backends_enabled = bool(values.experimental_backends_enabled)

    config.ac_lighting_enabled = bool(values.ac_lighting_enabled)
    config.battery_lighting_enabled = bool(values.battery_lighting_enabled)
    config.ac_lighting_brightness = clamp_brightness(values.ac_lighting_brightness)
    config.battery_lighting_brightness = clamp_brightness(values.battery_lighting_brightness)
    config.ac_power_mode = normalize_optional_power_mode(values.ac_power_mode)
    config.battery_power_mode = normalize_optional_power_mode(values.battery_power_mode)

    config.screen_dim_sync_enabled = bool(values.screen_dim_sync_enabled)

    mode = str(values.screen_dim_sync_mode or "off").strip().lower()
    config.screen_dim_sync_mode = mode if mode in {"off", "temp"} else "off"

    config.screen_dim_temp_brightness = clamp_nonzero_brightness(values.screen_dim_temp_brightness, default=5)

    config.idle_dim_debounce_enter_polls = max(1, min(60, int(values.idle_dim_debounce_enter_polls)))
    config.idle_dim_debounce_exit_polls = max(1, min(60, int(values.idle_dim_debounce_exit_polls)))

    config.time_scheduler_enabled = bool(values.time_scheduler_enabled)
    config.day_start_time = str(values.day_start_time or "08:00")
    config.night_start_time = str(values.night_start_time or "20:00")
    config.day_base_brightness = max(0, min(50, int(values.day_base_brightness)))
    config.day_reactive_brightness = max(0, min(50, int(values.day_reactive_brightness)))
    config.night_base_brightness = max(0, min(50, int(values.night_base_brightness)))
    config.night_reactive_brightness = max(0, min(50, int(values.night_reactive_brightness)))

    clock = datetime.now() if now is None else now
    active_reactive_brightness = settings_scheduler.active_scheduler_reactive_brightness(
        values,
        now=clock,
        clamp_brightness=clamp_brightness,
    )
    if active_reactive_brightness is not None:
        config.reactive_brightness = active_reactive_brightness

    layout = str(values.physical_layout or "auto").strip().lower()
    config.physical_layout = layout if layout in VALID_LAYOUT_IDS else "auto"
