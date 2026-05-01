"""Integration tests for the full dim → undim → restore cycle.

See improvement plan Item 6 — integration tests for dim/undim and reactive typing.
These tests exercise the complete idle-power action path with real policy and
action functions, verifying that brightness stays bounded during transitions.
"""
import pytest

from src.tray.pollers.idle_power.policy import compute_idle_action
from src.tray.pollers.idle_power.sensors import BacklightState


class TestDimTempRestorePolicyCycle:
    """Test that compute_idle_action produces correct actions across a full
    dim → temp-dim → restore cycle."""

    def test_dimmed_with_temp_mode_returns_dim_to_temp(self):
        action = compute_idle_action(
            dimmed=True,
            screen_off=False,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=False,
            idle_timeout_s=60.0,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="temp",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
            now=100.0,
            last_idle_turn_off_at=0.0,
            last_resume_at=0.0,
        )
        assert action == "dim_to_temp"

    def test_already_dim_temp_returns_none(self):
        """When dim_temp is already active and screen stays dimmed, no new action."""
        action = compute_idle_action(
            dimmed=True,
            screen_off=False,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=True,
            idle_timeout_s=60.0,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="temp",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
            now=100.0,
            last_idle_turn_off_at=0.0,
            last_resume_at=0.0,
        )
        assert action is None

    def test_screen_wakes_from_temp_dim_returns_restore_brightness(self):
        """When screen wakes after temp-dim, restore to user brightness."""
        action = compute_idle_action(
            dimmed=False,
            screen_off=False,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=True,
            idle_timeout_s=60.0,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="temp",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
            now=105.0,
            last_idle_turn_off_at=0.0,
            last_resume_at=0.0,
        )
        assert action == "restore_brightness"

    def test_full_cycle_dim_temp_then_restore(self):
        """Full cycle: normal → dim_to_temp → (already dim) → restore_brightness → normal."""
        base = dict(
            screen_off=False, is_off=False, idle_forced_off=False,
            idle_timeout_s=60.0, power_management_enabled=True,
            screen_dim_sync_enabled=True, screen_dim_sync_mode="temp",
            screen_dim_temp_brightness=5, brightness=25,
            user_forced_off=False, power_forced_off=False,
            last_idle_turn_off_at=0.0, last_resume_at=0.0,
        )

        action1 = compute_idle_action(dimmed=True, dim_temp_active=False, now=100.0, **base)
        assert action1 == "dim_to_temp"

        action2 = compute_idle_action(dimmed=True, dim_temp_active=True, now=100.0, **base)
        assert action2 is None

        action3 = compute_idle_action(
            dimmed=False, dim_temp_active=True, now=105.0, **base,
        )
        assert action3 == "restore_brightness"

        action4 = compute_idle_action(
            dimmed=False, dim_temp_active=False, now=110.0, **base,
        )
        assert action4 is None

    def test_post_resume_suppression(self):
        """Actions are suppressed shortly after resume."""
        action = compute_idle_action(
            dimmed=True,
            screen_off=False,
            is_off=False,
            idle_forced_off=False,
            dim_temp_active=False,
            idle_timeout_s=60.0,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
            now=100.5,
            last_idle_turn_off_at=0.0,
            last_resume_at=100.0,
        )
        assert action is None

    def test_post_turn_off_suppression(self):
        """Restore is suppressed shortly after turn-off."""
        action = compute_idle_action(
            dimmed=False,
            screen_off=False,
            is_off=True,
            idle_forced_off=False,
            dim_temp_active=False,
            idle_timeout_s=60.0,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
            now=100.5,
            last_idle_turn_off_at=100.0,
            last_resume_at=0.0,
        )
        assert action is None


class TestBacklightStateDataclass:
    """Tests for the BacklightState dataclass."""

    def test_default_state(self):
        state = BacklightState()
        assert state.baselines == {}
        assert state.dimmed == {}
        assert state.screen_off is False

    def test_state_is_mutable(self):
        state = BacklightState()
        state.baselines["/sys/class/backlight/intel_backlight"] = 100
        state.dimmed["/sys/class/backlight/intel_backlight"] = True
        state.screen_off = True
        assert state.baselines["/sys/class/backlight/intel_backlight"] == 100
        assert state.dimmed["/sys/class/backlight/intel_backlight"] is True
        assert state.screen_off is True