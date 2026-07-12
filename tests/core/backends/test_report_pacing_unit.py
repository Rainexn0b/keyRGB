from __future__ import annotations

from src.core.backends._report_pacing import (
    backend_report_delay_env_key,
    hid_report_delay_s_from_env,
    sleep_after_hid_report,
)


def test_backend_report_delay_env_key_normalizes_backend_names() -> None:
    assert backend_report_delay_env_key("ite8291r3_perkey") == "KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS"
    assert backend_report_delay_env_key("ite8258_perkey_chassis_logo_neon_vent_lenovo_legion") == "KEYRGB_ITE8258_PERKEY_CHASSIS_LOGO_NEON_VENT_LENOVO_LEGION_REPORT_DELAY_MS"
    assert backend_report_delay_env_key("ite8295_zones_lenovo_ideapad") == "KEYRGB_ITE8295_ZONES_LENOVO_IDEAPAD_REPORT_DELAY_MS"


def test_backend_report_delay_env_key_ignores_empty_names() -> None:
    assert backend_report_delay_env_key("") is None
    assert backend_report_delay_env_key("   ") is None


def test_backend_specific_delay_overrides_global(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_HID_REPORT_DELAY_MS", "9")
    monkeypatch.setenv("KEYRGB_ITE8258_PERKEY_CHASSIS_LOGO_NEON_VENT_LENOVO_LEGION_REPORT_DELAY_MS", "2.5")

    assert hid_report_delay_s_from_env(backend_name="ite8258_perkey_chassis_logo_neon_vent_lenovo_legion") == 0.0025


def test_invalid_backend_specific_delay_falls_back_to_global(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_HID_REPORT_DELAY_MS", "4")
    monkeypatch.setenv("KEYRGB_ITE8258_PERKEY_CHASSIS_LOGO_NEON_VENT_LENOVO_LEGION_REPORT_DELAY_MS", "not-a-number")

    assert hid_report_delay_s_from_env(backend_name="ite8258_perkey_chassis_logo_neon_vent_lenovo_legion") == 0.004


def test_sleep_after_hid_report_allows_zero_to_disable(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setenv("KEYRGB_ITE8258_PERKEY_CHASSIS_LOGO_NEON_VENT_LENOVO_LEGION_REPORT_DELAY_MS", "0")
    monkeypatch.setattr("src.core.backends._report_pacing.time.sleep", sleeps.append)

    sleep_after_hid_report(backend_name="ite8258_perkey_chassis_logo_neon_vent_lenovo_legion")

    assert sleeps == []
