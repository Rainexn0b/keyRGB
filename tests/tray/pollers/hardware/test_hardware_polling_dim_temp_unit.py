from __future__ import annotations

import threading
from types import SimpleNamespace

from keyrgb.core.effects.reactive.render import render
from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state


def test_hardware_polling_dim_temp_target_does_not_refresh_or_toggle_off() -> None:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(
        is_off=False,
        dim_temp_active=True,
        dim_temp_target_brightness=5,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
    )

    new_last_brightness, new_last_off = _apply_polled_hardware_state(
        tray,
        raw_brightness=5,
        current_brightness=5,
        current_off=False,
        last_brightness=10,
        last_off_state=None,
    )

    assert new_last_brightness == 5
    assert new_last_off is False
    assert tray.is_off is False
    tray._refresh_ui.assert_not_called()


def test_hardware_polling_ignores_zero_transient_while_dim_temp_active() -> None:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(
        is_off=False,
        dim_temp_active=True,
        dim_temp_target_brightness=5,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
    )

    new_last_brightness, new_last_off = _apply_polled_hardware_state(
        tray,
        raw_brightness=0,
        current_brightness=0,
        current_off=False,
        last_brightness=5,
        last_off_state=False,
    )

    assert new_last_brightness == 0
    assert new_last_off is False
    assert tray.is_off is False
    tray._refresh_ui.assert_not_called()


def test_hardware_polling_ignores_off_transient_while_dim_temp_active() -> None:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(
        is_off=False,
        dim_temp_active=True,
        dim_temp_target_brightness=5,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
    )

    new_last_brightness, new_last_off = _apply_polled_hardware_state(
        tray,
        raw_brightness=5,
        current_brightness=5,
        current_off=True,
        last_brightness=5,
        last_off_state=False,
    )

    assert new_last_brightness == 5
    assert new_last_off is False
    assert tray.is_off is False
    tray._refresh_ui.assert_not_called()


def test_invalid_high_render_heal_preserves_active_dim_target() -> None:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(
        is_off=False,
        dim_temp_active=True,
        dim_temp_target_brightness=5,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
    )
    tray.config.brightness = 40
    writes: list[int] = []

    class _Kb:
        backend_caps = SimpleNamespace(per_key=True)

        def set_brightness(self, brightness: int) -> None:
            writes.append(int(brightness))

        def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False) -> None:
            del enable_user_mode

    tray.engine = SimpleNamespace(
        running=True,
        brightness=5,
        reactive_brightness=50,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=50,
        _dim_temp_active=True,
        _hw_brightness_cap=None,
        kb=_Kb(),
        # EffectsEngine owns an RLock because render helpers may reinforce the
        # primary-write boundary while the frame commit already holds it.
        kb_lock=threading.RLock(),
        _last_hw_mode_brightness=5,
        _last_rendered_brightness=5,
        _last_reactive_per_key_frame_signature=("sig",),
    )

    result = _apply_polled_hardware_state(
        tray,
        raw_brightness=60,
        current_brightness=50,
        current_off=False,
        last_brightness=50,
        last_off_state=False,
    )

    assert result == (50, False)
    assert tray.engine.brightness == 5
    assert tray.engine._last_rendered_brightness == 50
    assert tray.engine._last_hw_mode_brightness == 60
    assert tray.config.brightness == 40
    assert tray.engine._reactive_state._reactive_controller_brightness_handoff_active is True

    for _frame in range(6):
        render(tray.engine, color_map={(0, 0): (255, 255, 255)})

    assert writes == [42, 34, 26, 18, 10, 5]
    assert tray.engine._last_hw_mode_brightness == 5
    assert tray.engine._reactive_state._reactive_controller_brightness_handoff_active is False


def test_hardware_polling_never_clears_is_off_when_user_forced_off() -> None:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(
        is_off=True,
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        power_forced_off=False,
        user_forced_off=True,
        idle_forced_off=False,
    )

    _apply_polled_hardware_state(
        tray,
        raw_brightness=10,
        current_brightness=10,
        current_off=False,
        last_brightness=0,
        last_off_state=None,
    )

    assert tray.is_off is True


def test_hardware_polling_can_clear_is_off_when_not_forced_off() -> None:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(
        is_off=True,
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
    )

    _apply_polled_hardware_state(
        tray,
        raw_brightness=10,
        current_brightness=10,
        current_off=False,
        last_brightness=0,
        last_off_state=None,
    )

    assert tray.is_off is False
