from __future__ import annotations

from pathlib import Path

import src.tray.pollers.idle_power._desktop_timeout as desktop_timeout


def test_read_kde_dim_timeout_returns_ac_timeout(tmp_path: Path) -> None:
    config = tmp_path / "powerdevilrc"
    config.write_text(
        "[AC][Display]\nDimDisplayIdleTimeoutSec=10\n"
        "[Battery][Display]\nDimDisplayIdleTimeoutSec=30\n",
        encoding="utf-8",
    )

    assert desktop_timeout.read_kde_dim_timeout(True, config_home=tmp_path) == 10.0


def test_read_kde_dim_timeout_returns_battery_timeout(tmp_path: Path) -> None:
    config = tmp_path / "powerdevilrc"
    config.write_text(
        "[AC][Display]\nDimDisplayIdleTimeoutSec=10\n"
        "[Battery][Display]\nDimDisplayIdleTimeoutSec=30\n",
        encoding="utf-8",
    )

    assert desktop_timeout.read_kde_dim_timeout(False, config_home=tmp_path) == 30.0


def test_read_kde_dim_timeout_defaults_to_ac_when_power_source_unknown(tmp_path: Path) -> None:
    config = tmp_path / "powerdevilrc"
    config.write_text(
        "[AC][Display]\nDimDisplayIdleTimeoutSec=10\n"
        "[Battery][Display]\nDimDisplayIdleTimeoutSec=30\n",
        encoding="utf-8",
    )

    assert desktop_timeout.read_kde_dim_timeout(None, config_home=tmp_path) == 10.0


def test_read_kde_dim_timeout_returns_none_when_profile_has_no_dim_key(tmp_path: Path) -> None:
    config = tmp_path / "powerdevilrc"
    config.write_text(
        "[AC][Display]\nTurnOffDisplayIdleTimeoutSec=900\n"
        "[Battery][Display]\nDimDisplayIdleTimeoutSec=30\n",
        encoding="utf-8",
    )

    assert desktop_timeout.read_kde_dim_timeout(True, config_home=tmp_path) is None


def test_read_kde_dim_timeout_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert desktop_timeout.read_kde_dim_timeout(True, config_home=tmp_path) is None


def test_read_kde_dim_timeout_ignores_negative_timeout(tmp_path: Path) -> None:
    config = tmp_path / "powerdevilrc"
    config.write_text(
        "[AC][Display]\nDimDisplayIdleTimeoutSec=-2\n",
        encoding="utf-8",
    )

    assert desktop_timeout.read_kde_dim_timeout(True, config_home=tmp_path) is None
