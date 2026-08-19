"""Desktop-session config plus idle-policy composition."""

from __future__ import annotations

from pathlib import Path

from keyrgb.tray.pollers.idle_power._desktop_timeout import read_kde_dim_timeout
from keyrgb.tray.pollers.idle_power.policy import compute_idle_action


def test_kde_session_dim_timeout_drives_idle_policy_action(tmp_path: Path) -> None:
    config_home = tmp_path / "xdg-config"
    config_home.mkdir()
    (config_home / "powerdevilrc").write_text(
        "[AC][Display]\nDimDisplayIdleTimeoutSec=45\n[Battery][Display]\nDimDisplayIdleTimeoutSec=15\n",
        encoding="utf-8",
    )

    timeout_s = read_kde_dim_timeout(True, config_home=config_home)
    assert timeout_s == 45.0

    action = compute_idle_action(
        dimmed=True,
        screen_off=False,
        is_off=False,
        idle_forced_off=False,
        dim_temp_active=False,
        idle_timeout_s=timeout_s,
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
