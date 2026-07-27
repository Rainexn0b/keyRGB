"""Compatibility smoke tests for explicitly preserved extraction facades."""

from __future__ import annotations


def test_profile_default_name_compatibility_alias() -> None:
    from src.core.profile import profiles

    assert profiles._DEFAULT_PROFILE == profiles.DEFAULT_PROFILE_NAME
    assert "_DEFAULT_PROFILE" in profiles.__all__


def test_lighting_mode_compatibility_facade() -> None:
    from src.tray.controllers import _lighting_controller_helpers as facade, _lighting_mode_apply as owner

    assert facade.apply_perkey_mode is owner.apply_perkey_mode
    assert facade.apply_uniform_none_mode is owner.apply_uniform_none_mode


def test_hardware_recovery_compatibility_facade() -> None:
    from src.tray.pollers import hardware_polling as facade
    from src.tray.pollers.hardware import _recovery as owner

    assert facade._execute_blank_recovery is owner._execute_blank_recovery
    assert facade._power_source_blank_recovery_eligible is owner._power_source_blank_recovery_eligible
    assert facade._resolve_tray_callback is owner._resolve_tray_callback


def test_reactive_brightness_compatibility_facade() -> None:
    from src.core.effects.reactive import (
        _reactive_restore_seed as restore_owner,
        _reactive_transition_atomic as atomic_owner,
        _render_brightness_support as facade,
    )

    assert facade.seed_reactive_restore_windows is restore_owner.seed_reactive_restore_windows
    assert facade.seed_transition_atomic is atomic_owner.seed_transition_atomic
    assert facade.read_transition_atomic is atomic_owner.read_transition_atomic


def test_profile_action_compatibility_facade() -> None:
    from src.gui.perkey.ui import _profile_actions_ui as owner, profile_actions as facade

    assert facade.activate_profile_ui is owner.activate_profile_ui
    assert facade.save_profile_ui is owner.save_profile_ui
    assert facade.KEEP_CURRENT_PROFILE_LABEL == owner.KEEP_CURRENT_PROFILE_LABEL


def test_power_manager_poll_interval_monkeypatch_seam() -> None:
    from src.core.power.management import _manager_battery_saver as owner, manager as facade

    assert facade._DEFAULT_POWER_SOURCE_POLL_INTERVAL_S == owner._DEFAULT_POWER_SOURCE_POLL_INTERVAL_S
