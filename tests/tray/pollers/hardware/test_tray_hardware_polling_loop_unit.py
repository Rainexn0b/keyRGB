from __future__ import annotations

import pytest


def test_normalize_brightness_invalid_returns_zero() -> None:
    from keyrgb.tray.pollers.hardware_polling import _normalize_brightness_to_config_scale

    assert _normalize_brightness_to_config_scale("nope") == 0  # type: ignore[arg-type]


def test_apply_polled_state_logs_brightness_change_but_swallows_log_errors(
    monkeypatch,
) -> None:
    from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state
    from tests.tray.fakes import make_owner_backed_simple_tray

    def boom(*_a, **_kw):
        raise RuntimeError("boom")

    tray = make_owner_backed_simple_tray(
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        _refresh_ui=lambda: None,
        _log_event=boom,
    )

    # last_brightness changes => tries to log; log throws; should still refresh and return.
    b, off = _apply_polled_hardware_state(
        tray,
        raw_brightness=None,
        current_brightness=10,
        current_off=False,
        last_brightness=5,
        last_off_state=None,
    )

    assert b == 10
    assert off is False


def test_apply_polled_state_logs_off_state_change_but_swallows_log_errors() -> None:
    from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state

    refreshed = {"n": 0}
    animate_flags: list[bool] = []

    def boom(*_a, **_kw):
        raise RuntimeError("boom")

    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        _refresh_ui=lambda *, animate_icon=True: (
            refreshed.__setitem__("n", refreshed["n"] + 1),
            animate_flags.append(bool(animate_icon)),
        ),
        _log_event=boom,
        is_off=False,
    )

    b, off = _apply_polled_hardware_state(
        tray,
        raw_brightness=5,
        current_brightness=5,
        current_off=True,
        last_brightness=None,
        last_off_state=False,
    )

    assert (b, off) == (5, True)
    assert tray.is_off is True
    assert refreshed["n"] == 1
    assert animate_flags == [False]


def test_apply_polled_state_propagates_unexpected_log_event_errors() -> None:
    from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state
    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        _refresh_ui=lambda: None,
        _log_event=lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("unexpected event bug")),
        is_off=False,
    )

    with pytest.raises(AssertionError, match="unexpected event bug"):
        _apply_polled_hardware_state(
            tray,
            raw_brightness=None,
            current_brightness=10,
            current_off=False,
            last_brightness=5,
            last_off_state=None,
        )


def test_apply_polled_state_dim_temp_target_bad_int_is_ignored(monkeypatch) -> None:
    from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state

    class BadInt:
        def __int__(self):
            raise TypeError("no")

    refreshed = {"n": 0}

    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(
        dim_temp_active=True,
        dim_temp_target_brightness=BadInt(),
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        _refresh_ui=lambda: refreshed.__setitem__("n", refreshed["n"] + 1),
        _log_event=None,
        is_off=False,
    )

    _apply_polled_hardware_state(
        tray,
        raw_brightness=7,
        current_brightness=7,
        current_off=False,
        last_brightness=9,
        last_off_state=None,
    )

    assert refreshed["n"] == 1


def test_apply_polled_state_off_state_change_branch_and_forced_off_gate() -> None:
    from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state

    refreshed = {"n": 0}

    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        power_forced_off=True,
        user_forced_off=False,
        idle_forced_off=False,
        _refresh_ui=lambda: refreshed.__setitem__("n", refreshed["n"] + 1),
        _log_event=lambda *_a, **_kw: None,
        is_off=False,
    )

    # Off-state flips to True while power-forced-off => should return early with no UI refresh.
    b, off = _apply_polled_hardware_state(
        tray,
        raw_brightness=5,
        current_brightness=5,
        current_off=True,
        last_brightness=None,
        last_off_state=False,
    )

    assert (b, off) == (5, True)
    assert refreshed["n"] == 0


def test_apply_polled_state_off_state_change_clears_unforced_logical_off() -> None:
    from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state
    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        _refresh_ui=lambda **_kwargs: None,
        _log_event=lambda *_args, **_kwargs: None,
        is_off=True,
    )

    result = _apply_polled_hardware_state(
        tray,
        raw_brightness=5,
        current_brightness=5,
        current_off=False,
        last_brightness=5,
        last_off_state=True,
    )

    assert result == (5, False)
    assert tray.is_off is False


def test_apply_polled_state_off_change_adopts_successful_recent_blank_recovery(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp
    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        _refresh_ui=lambda **_kwargs: None,
        _log_event=lambda *_args, **_kwargs: None,
        is_off=False,
    )
    monkeypatch.setattr(hp, "_recover_recent_power_source_blank_best_effort", lambda *_args, **_kwargs: True)

    result = hp._apply_polled_hardware_state(
        tray,
        raw_brightness=5,
        current_brightness=5,
        current_off=True,
        last_brightness=5,
        last_off_state=False,
    )

    assert result == (5, False)
