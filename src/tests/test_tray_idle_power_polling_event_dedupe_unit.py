from __future__ import annotations

from src.tray.pollers import idle_power_polling as ipp


def test_build_idle_action_key_is_stable_for_inputs():
    key = ipp._build_idle_action_key(
        action="dim_to_temp",
        dimmed=True,
        screen_off=False,
        brightness=10,
        dim_sync_mode="dim",
        dim_temp_brightness=5,
    )
    assert "dim_to_temp" in key
    assert "dimmed=True" in key
    assert "screen_off=False" in key
    assert "bri=10" in key
    assert "dim_mode=dim" in key
    assert "dim_tmp=5" in key


def test_build_idle_action_key_changes_when_inputs_change() -> None:
    base = ipp._build_idle_action_key(
        action="turn_off",
        dimmed=True,
        screen_off=False,
        brightness=10,
        dim_sync_mode="off",
        dim_temp_brightness=5,
    )
    changed_brightness = ipp._build_idle_action_key(
        action="turn_off",
        dimmed=True,
        screen_off=False,
        brightness=11,
        dim_sync_mode="off",
        dim_temp_brightness=5,
    )
    changed_screen_off = ipp._build_idle_action_key(
        action="turn_off",
        dimmed=True,
        screen_off=True,
        brightness=10,
        dim_sync_mode="off",
        dim_temp_brightness=5,
    )
    assert base != changed_brightness
    assert base != changed_screen_off


def test_should_log_idle_action_rejects_none_action():
    assert ipp._should_log_idle_action(action="none", action_key="x", last_action_key=None) is False


def test_should_log_idle_action_logs_first_real_action():
    assert ipp._should_log_idle_action(action="turn_off", action_key="k1", last_action_key=None) is True


def test_should_log_idle_action_dedupes_by_action_key():
    assert ipp._should_log_idle_action(action="turn_off", action_key="k1", last_action_key="k1") is False
    assert ipp._should_log_idle_action(action="turn_off", action_key="k2", last_action_key="k1") is True
