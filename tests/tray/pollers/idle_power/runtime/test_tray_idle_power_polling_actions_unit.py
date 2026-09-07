from __future__ import annotations

from types import SimpleNamespace

from tests.tray.fakes import make_owner_backed_simple_tray


def test_apply_idle_action_dim_to_temp_respects_is_off_and_sw_effect(
    monkeypatch,
) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    engine_calls = {"n": 0, "apply_to_hardware": None}

    def set_brightness(v: int, *, apply_to_hardware: bool):
        engine_calls["n"] += 1
        engine_calls["apply_to_hardware"] = apply_to_hardware

    tray = make_owner_backed_simple_tray(
        is_off=False,
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        config=SimpleNamespace(effect="perkey"),
        engine=SimpleNamespace(set_brightness=set_brightness),
    )

    ipp._apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=5)

    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 5
    assert tray.tray_idle_power_state.dim_temp_active is True
    assert engine_calls["n"] == 1
    # perkey is a hardware per-key apply path -> DO apply to hardware
    assert engine_calls["apply_to_hardware"] is True

    tray_sw = make_owner_backed_simple_tray(
        is_off=False,
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        config=SimpleNamespace(effect="rainbow_wave"),
        engine=SimpleNamespace(set_brightness=set_brightness),
    )
    ipp._apply_idle_action(tray_sw, action="dim_to_temp", dim_temp_brightness=5)
    assert engine_calls["n"] == 2
    assert engine_calls["apply_to_hardware"] is False

    tray2 = make_owner_backed_simple_tray(
        is_off=True,
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        config=SimpleNamespace(effect="uniform"),
        engine=SimpleNamespace(set_brightness=set_brightness),
    )

    ipp._apply_idle_action(tray2, action="dim_to_temp", dim_temp_brightness=5)
    assert engine_calls["n"] == 2  # unchanged; skipped when off


def test_apply_idle_action_restore_branch_gated_by_forced_off(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    called = {"n": 0}

    monkeypatch.setattr(
        "keyrgb.tray.pollers.idle_power._actions.restore_from_idle",
        lambda _tray: called.__setitem__("n", called["n"] + 1),
    )

    tray = make_owner_backed_simple_tray(user_forced_off=True, power_forced_off=False)
    ipp._apply_idle_action(tray, action="restore", dim_temp_brightness=5)
    assert called["n"] == 0

    tray2 = make_owner_backed_simple_tray(user_forced_off=False, power_forced_off=True)
    ipp._apply_idle_action(tray2, action="restore", dim_temp_brightness=5)
    assert called["n"] == 0

    tray3 = make_owner_backed_simple_tray(
        user_forced_off=False,
        power_forced_off=False,
        idle_forced_off=True,
        config=SimpleNamespace(),
    )
    ipp._apply_idle_action(tray3, action="restore", dim_temp_brightness=5)
    assert called["n"] == 1
