"""Runtime-boundary dependency loaders for power management."""

from __future__ import annotations


def monitor_acpi_events(*args, **kwargs):
    from src.core.power.monitoring.acpi_monitoring import monitor_acpi_events as _monitor_acpi_events

    return _monitor_acpi_events(*args, **kwargs)


def start_sysfs_lid_monitoring(*args, **kwargs):
    from src.core.power.monitoring.lid_monitoring import start_sysfs_lid_monitoring as _start_sysfs_lid_monitoring

    return _start_sysfs_lid_monitoring(*args, **kwargs)


def monitor_prepare_for_sleep(*args, **kwargs):
    from src.core.power.monitoring.login1_monitoring import monitor_prepare_for_sleep as _monitor_prepare_for_sleep

    return _monitor_prepare_for_sleep(*args, **kwargs)


def read_on_ac_power(*args, **kwargs):
    from src.core.power.monitoring.power_supply_sysfs import read_on_ac_power as _read_on_ac_power

    return _read_on_ac_power(*args, **kwargs)


def get_active_profile(*args, **kwargs):
    from src.core.profile.paths import get_active_profile as _get_active_profile

    return _get_active_profile(*args, **kwargs)


def safe_int_attr(*args, **kwargs):
    from src.core.utils.safe_attrs import safe_int_attr as _safe_int_attr

    return _safe_int_attr(*args, **kwargs)