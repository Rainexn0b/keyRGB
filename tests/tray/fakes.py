"""Shared duck-typed tray fakes for unit tests.

Prefer attaching a real ``TrayIdlePowerState`` so production helpers exercise the
typed owner path instead of only legacy private attrs.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from src.tray.idle_power_state import TrayIdlePowerState


def make_idle_power_owner(
    *,
    user_forced_off: bool = False,
    power_forced_off: bool = False,
    idle_forced_off: bool = False,
    dim_temp_active: bool = False,
    dim_temp_target_brightness: int | None = None,
    last_brightness: int = 25,
    last_resume_at: float = 0.0,
    **extra: Any,
) -> TrayIdlePowerState:
    return TrayIdlePowerState(
        user_forced_off=user_forced_off,
        power_forced_off=power_forced_off,
        idle_forced_off=idle_forced_off,
        dim_temp_active=dim_temp_active,
        dim_temp_target_brightness=dim_temp_target_brightness,
        last_brightness=last_brightness,
        last_resume_at=last_resume_at,
        **extra,
    )


def attach_idle_power_owner(tray: object, owner: TrayIdlePowerState | None = None) -> TrayIdlePowerState:
    """Attach owner and mirror compatibility attrs used by dual-write helpers."""

    st = owner if isinstance(owner, TrayIdlePowerState) else make_idle_power_owner()
    try:
        setattr(tray, "tray_idle_power_state", st)
    except AttributeError:
        pass
    # Mirror for tests that still read legacy private attrs directly.
    for attr, field in (
        ("_user_forced_off", "user_forced_off"),
        ("_power_forced_off", "power_forced_off"),
        ("_idle_forced_off", "idle_forced_off"),
        ("_dim_temp_active", "dim_temp_active"),
        ("_dim_temp_target_brightness", "dim_temp_target_brightness"),
        ("_last_brightness", "last_brightness"),
        ("_last_resume_at", "last_resume_at"),
    ):
        try:
            setattr(tray, attr, getattr(st, field))
        except AttributeError:
            pass
    return st


def make_owner_backed_simple_tray(**fields: Any) -> SimpleNamespace:
    owner_kwargs = {
        key: fields.pop(key)
        for key in (
            "user_forced_off",
            "power_forced_off",
            "idle_forced_off",
            "dim_temp_active",
            "dim_temp_target_brightness",
            "last_brightness",
            "last_resume_at",
        )
        if key in fields
    }
    # Accept legacy private-attr names as aliases for owner seed values.
    legacy_map = {
        "_user_forced_off": "user_forced_off",
        "_power_forced_off": "power_forced_off",
        "_idle_forced_off": "idle_forced_off",
        "_dim_temp_active": "dim_temp_active",
        "_dim_temp_target_brightness": "dim_temp_target_brightness",
        "_last_brightness": "last_brightness",
        "_last_resume_at": "last_resume_at",
    }
    for legacy, owner_name in legacy_map.items():
        if legacy in fields and owner_name not in owner_kwargs:
            owner_kwargs[owner_name] = fields.pop(legacy)

    tray = SimpleNamespace(**fields)
    attach_idle_power_owner(tray, make_idle_power_owner(**owner_kwargs))
    return tray


def make_owner_backed_mock_tray(**fields: Any) -> MagicMock:
    owner_kwargs = {
        key: fields.pop(key)
        for key in (
            "user_forced_off",
            "power_forced_off",
            "idle_forced_off",
            "dim_temp_active",
            "dim_temp_target_brightness",
            "last_brightness",
            "last_resume_at",
        )
        if key in fields
    }
    legacy_map = {
        "_user_forced_off": "user_forced_off",
        "_power_forced_off": "power_forced_off",
        "_idle_forced_off": "idle_forced_off",
        "_dim_temp_active": "dim_temp_active",
        "_dim_temp_target_brightness": "dim_temp_target_brightness",
        "_last_brightness": "last_brightness",
        "_last_resume_at": "last_resume_at",
    }
    for legacy, owner_name in legacy_map.items():
        if legacy in fields and owner_name not in owner_kwargs:
            owner_kwargs[owner_name] = fields.pop(legacy)

    tray = MagicMock()
    for key, value in fields.items():
        setattr(tray, key, value)
    attach_idle_power_owner(tray, make_idle_power_owner(**owner_kwargs))
    return tray
