"""Power-mode save, status formatting, and cap helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from keyrgb.gui.windows import power_mode
from tests.gui.windows.power_mode._power_mode_fakes import _FakeVar


def test_save_persists_clamped_extreme_cap_and_refreshes_status(monkeypatch) -> None:
    gui = power_mode.PowerModeSettingsGUI.__new__(power_mode.PowerModeSettingsGUI)
    config = SimpleNamespace(system_power_extreme_cap_khz=800_000)
    gui.config = config
    gui._cap_var = _FakeVar(123.0)
    gui._cap_value_var = _FakeVar("")
    gui._save_status_var = _FakeVar("")
    gui._status_var = _FakeVar("")
    refreshed: list[str] = []
    gui._refresh_status = lambda: refreshed.append("status")
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=True, mode=SimpleNamespace(value="balanced"), reason="ok", identifiers={}),
    )

    gui._save()

    assert config.system_power_extreme_cap_khz == 400_000
    assert gui._cap_value_var.get() == "400 MHz"
    assert "Extreme Saver target" in gui._save_status_var.get()
    assert refreshed == ["status"]


def test_save_reapplies_extreme_saver_when_active(monkeypatch) -> None:
    gui = power_mode.PowerModeSettingsGUI.__new__(power_mode.PowerModeSettingsGUI)
    config = SimpleNamespace(system_power_extreme_cap_khz=800_000)
    gui.config = config
    gui._cap_var = _FakeVar(1004.0)
    gui._cap_value_var = _FakeVar("")
    gui._save_status_var = _FakeVar("")
    gui._status_var = _FakeVar("")
    refreshed: list[str] = []
    reapplied: list[power_mode.PowerMode] = []
    gui._refresh_status = lambda: refreshed.append("status")
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=True, mode=power_mode.PowerMode.EXTREME_SAVER, reason="ok", identifiers={}),
    )
    monkeypatch.setattr(power_mode, "set_mode", lambda mode: reapplied.append(mode) or True)

    gui._save()

    assert config.system_power_extreme_cap_khz == 1_004_000
    assert gui._cap_value_var.get() == "1004 MHz"
    assert gui._save_status_var.get() == "Saved and reapplied Extreme Saver."
    assert reapplied == [power_mode.PowerMode.EXTREME_SAVER]
    assert refreshed == ["status"]


def test_format_status_text_includes_apply_path_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(
            supported=True,
            mode=SimpleNamespace(value="extreme-saver"),
            reason="ok",
            identifiers={
                "can_apply": "false",
                "helper_present": "false",
                "sysfs_writable": "false",
                "configured_extreme_cap_khz": "1004000",
            },
        ),
    )

    text = power_mode._format_status_text()

    assert "Current mode: Extreme Saver" in text
    assert "Can apply: no" in text
    assert "Helper installed: no" in text
    assert "Configured target: 1004 MHz" in text


def test_format_live_freq_text_formats_average_mhz(monkeypatch) -> None:
    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (612_500, 1_017_000))

    text = power_mode._format_live_freq_text()

    assert text == "Live CPU avg/max: 612 / 1017 MHz"


def test_format_status_text_error_and_unsupported(monkeypatch) -> None:
    monkeypatch.setattr(power_mode, "get_status", lambda: (_ for _ in ()).throw(OSError("nope")))
    assert power_mode._format_status_text() == "Status: unavailable"

    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=False, reason="", mode=None, identifiers={}),
    )
    assert "unavailable" in power_mode._format_status_text()

    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(
            supported=True,
            mode=SimpleNamespace(value="balanced"),
            reason="ok",
            identifiers={
                "can_apply": "true",
                "helper_present": "true",
                "sysfs_writable": "true",
                "configured_extreme_cap_khz": "not-int",
            },
        ),
    )
    text = power_mode._format_status_text()
    assert "Balanced" in text
    assert "Configured target" not in text


def test_format_live_freq_text_error_paths(monkeypatch) -> None:
    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert power_mode._format_live_freq_text() == "Live CPU avg/max: unavailable"

    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (None, None))
    assert power_mode._format_live_freq_text() == "Live CPU avg/max: unavailable"

    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (500_000, None))
    assert power_mode._format_live_freq_text() == "Live CPU avg/max: 500 MHz / unavailable"


def test_mode_title_and_cap_helpers() -> None:
    assert power_mode._mode_title(None) == "Unknown"
    assert power_mode._mode_title("extreme-saver") == "Extreme Saver"
    assert power_mode._cap_mhz_bounds()[0] < power_mode._cap_mhz_bounds()[1]
    assert "MHz" in power_mode._format_cap_mhz_label(1_000_000)


def test_save_not_extreme_and_set_mode_failure(monkeypatch) -> None:

    config = SimpleNamespace(system_power_extreme_cap_khz=800_000)
    gui = SimpleNamespace(
        config=config,
        _selected_cap_khz=lambda: 900_000,
        _cap_value_var=SimpleNamespace(set=MagicMock()),
        _save_status_var=SimpleNamespace(set=MagicMock()),
        _refresh_status=MagicMock(),
    )
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=True, mode=power_mode.PowerMode.BALANCED),
    )
    monkeypatch.setattr(power_mode, "_format_cap_mhz_label", lambda khz: f"{khz}")
    power_mode.PowerModeSettingsGUI._save(gui)
    assert "next time" in gui._save_status_var.set.call_args.args[0]

    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=True, mode=power_mode.PowerMode.EXTREME_SAVER),
    )
    monkeypatch.setattr(power_mode, "set_mode", lambda _m: False)
    power_mode.PowerModeSettingsGUI._save(gui)
    assert "Re-select Extreme Saver" in gui._save_status_var.set.call_args.args[0]

    monkeypatch.setattr(power_mode, "set_mode", lambda _m: (_ for _ in ()).throw(OSError("fail")))
    power_mode.PowerModeSettingsGUI._save(gui)
    assert "Re-select Extreme Saver" in gui._save_status_var.set.call_args.args[0]
