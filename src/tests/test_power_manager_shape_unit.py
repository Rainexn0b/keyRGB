from __future__ import annotations

from src.core.power_management import PowerManager


def test_power_manager_has_expected_methods() -> None:
    # Guards against accidental indentation/scope regressions.
    assert callable(getattr(PowerManager, "_monitor_loop", None))
    assert callable(getattr(PowerManager, "_on_resume", None))
    assert callable(getattr(PowerManager, "_battery_saver_loop", None))
