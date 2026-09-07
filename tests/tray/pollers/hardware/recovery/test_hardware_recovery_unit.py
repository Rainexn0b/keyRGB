"""Direct unit tests for power-source blank eligibility."""

from __future__ import annotations

from keyrgb.tray.pollers.hardware._recovery import _power_source_blank_recovery_eligible
from tests.tray.fakes import make_owner_backed_simple_tray


def _make_recovery_tray(**extra) -> object:
    """Build an owner-backed tray with recovery-relevant attrs preset."""

    config = extra.pop("config_brightness", 25)
    tray = make_owner_backed_simple_tray(
        last_brightness=extra.pop("last_brightness", 25),
        config=type("C", (), {"brightness": config})(),
        **extra,
    )
    return tray


def _set_recovery_stamps(tray: object, *, hardware: float | None = None) -> None:
    tray._last_power_source_transition_at = 0.0 if hardware is not None else 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    if hardware is not None:
        tray._last_hardware_blank_recovery_at = hardware


def test_power_source_blank_recovery_eligible_when_conditions_met() -> None:
    """All conditions satisfied: recent transition, no forced off, intent > 0, cooldown elapsed."""

    tray = _make_recovery_tray()
    _set_recovery_stamps(tray)

    assert _power_source_blank_recovery_eligible(tray, now=101.0) is True


def test_power_source_blank_recovery_not_eligible_outside_window() -> None:
    """Transition was too long ago — outside the recovery window."""

    tray = _make_recovery_tray()
    _set_recovery_stamps(tray)

    # window_s is 6.0 by default; 110 - 100 = 10 > 6
    assert _power_source_blank_recovery_eligible(tray, now=110.0) is False


def test_power_source_blank_recovery_not_eligible_when_forced_off() -> None:
    tray = _make_recovery_tray(power_forced_off=True)
    _set_recovery_stamps(tray)

    assert _power_source_blank_recovery_eligible(tray, now=101.0) is False


def test_power_source_blank_recovery_not_eligible_when_brightness_intent_zero() -> None:
    tray = _make_recovery_tray(config_brightness=0, last_brightness=0)
    _set_recovery_stamps(tray)

    assert _power_source_blank_recovery_eligible(tray, now=101.0) is False


def test_power_source_blank_recovery_not_eligible_immediately_after_resume() -> None:
    """A lid/power restore fade must not be fought by a blank-heal."""

    tray = _make_recovery_tray()
    _set_recovery_stamps(tray)
    tray._last_resume_at = 100.0

    assert _power_source_blank_recovery_eligible(tray, now=101.0) is False
    assert _power_source_blank_recovery_eligible(tray, now=103.0) is True


def test_power_source_blank_recovery_not_eligible_within_cooldown() -> None:
    """Recovery was attempted very recently — must wait for cooldown."""

    tray = _make_recovery_tray()
    _set_recovery_stamps(tray)
    tray._last_power_source_blank_recovery_at = 100.5

    # cooldown_s is 0.75 by default; 101.0 - 100.5 = 0.5 < 0.75
    assert _power_source_blank_recovery_eligible(tray, now=101.0) is False


def test_power_source_blank_recovery_uses_monotonic_when_now_is_none(monkeypatch) -> None:
    """When now=None, the function falls back to time.monotonic()."""

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 101.0)

    tray = _make_recovery_tray()
    _set_recovery_stamps(tray)

    assert _power_source_blank_recovery_eligible(tray) is True


def test_power_source_blank_recovery_coerces_bad_last_recovery_at_to_zero() -> None:
    """A non-float last_recovery_at should not crash; defaults to 0.0."""

    tray = _make_recovery_tray()
    _set_recovery_stamps(tray)
    tray._last_power_source_blank_recovery_at = "not-a-float"  # type: ignore[assignment]

    # Should not raise; treat corrupt value as 0.0 (eligible since cooldown 101 - 0 > 0.75).
    assert _power_source_blank_recovery_eligible(tray, now=101.0) is True
